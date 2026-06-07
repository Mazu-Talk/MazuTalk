import { useMemo, useRef, useState } from 'react'
import './styles.css'

type SpeechAnalysis = {
  duration_seconds: number
  word_count: number
  pace: {
    words_per_minute: number
    syllables_per_second: number
    label: string
  }
  repetition_score: number
  repeated_expressions: Array<{
    expression: string
    count: number
    type: string
  }>
  response_latency: {
    seconds: number | null
    label: string
  }
  flags: string[]
  coaching_tips: string[]
}

type DialogueResponse = {
  analysis: SpeechAnalysis
  llm: {
    therapist_reply: string
    next_prompt: string
    coaching_cues: string[]
    model_name: string
  }
}

type SttPipelineResponse = DialogueResponse & {
  session_id: string
  transcript: string
  stt_model: string
  stt_time_seconds: number
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const modelResults = [
  { model: 'tiny', condition: 'raw/full wav', sampleCount: 100, cer: 0.2747, avgTime: 1.068 },
  { model: 'small', condition: 'cropped + tuned', sampleCount: 100, cer: 0.1018, avgTime: 3.551 },
  { model: 'medium', condition: 'cropped + tuned', sampleCount: 100, cer: 0.0515, avgTime: 8.531 },
]

const sttSamples = [
  {
    id: 'sample-1',
    fileName: 'K00017115-BFG30-L1N2D2-E-K0KK-04639114.wav',
    reference: '엄마는 아무것도 아니라고 하시지만 난 금요일이 너무 좋다.',
    smallText: '엄마는 아무것도 아니라고 하시지만 난 금요일이 너무 좋다.',
    duration: 6,
    latency: 1.2,
  },
  {
    id: 'sample-2',
    fileName: 'K00016901-BFG33-L1N2D1-E-K0KK-04047208.wav',
    reference: '우리는 시간이 되어서 기차를 타러 내려갔다',
    smallText: '우리는 시간이 되어서 기차를 타러 내려왔다.',
    duration: 5,
    latency: 2.5,
  },
  {
    id: 'sample-3',
    fileName: 'K00013970-BMG30-L1N2D1-E-K0KK-02104030.wav',
    reference: '도서관은 평소 보다 사람이 적어 조용했다',
    smallText: '도려가는 평소보다 사람이 저거 조용했다.',
    duration: 4.5,
    latency: 4.8,
  },
]

export default function App() {
  const [selectedSampleId, setSelectedSampleId] = useState(sttSamples[0].id)
  const [transcript, setTranscript] = useState(sttSamples[0].smallText)
  const [duration, setDuration] = useState(sttSamples[0].duration)
  const [latency, setLatency] = useState(sttSamples[0].latency)
  const [analysis, setAnalysis] = useState<SpeechAnalysis | null>(null)
  const [dialogue, setDialogue] = useState<DialogueResponse | null>(null)
  const [liveResult, setLiveResult] = useState<SttPipelineResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState('')
  const selectedSample = sttSamples.find((sample) => sample.id === selectedSampleId) ?? sttSamples[0]
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const promptRequestedAtRef = useRef<Date | null>(null)
  const recordingStartedAtRef = useRef<Date | null>(null)

  const sttPayload = useMemo(() => {
    const requestedAt = new Date()
    const startedAt = new Date(requestedAt.getTime() + latency * 1000)

    return {
      transcript,
      duration_seconds: duration,
      response_requested_at: requestedAt.toISOString(),
      response_started_at: startedAt.toISOString(),
    }
  }, [duration, latency, transcript])

  async function postJson<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      throw new Error(`API ${response.status}: ${await response.text()}`)
    }

    return response.json()
  }

  async function postForm<T>(path: string, body: FormData): Promise<T> {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: 'POST',
      body,
    })

    if (!response.ok) {
      throw new Error(`API ${response.status}: ${await response.text()}`)
    }

    return response.json()
  }

  function selectSample(sampleId: string) {
    const sample = sttSamples.find((item) => item.id === sampleId)
    if (!sample) {
      return
    }

    setSelectedSampleId(sample.id)
    setTranscript(sample.smallText)
    setDuration(sample.duration)
    setLatency(sample.latency)
    setAnalysis(null)
    setDialogue(null)
    setLiveResult(null)
    setError('')
  }

  function markPromptStart() {
    promptRequestedAtRef.current = new Date()
    setError('')
    setLiveResult(null)
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('현재 브라우저에서 마이크 녹음을 사용할 수 없습니다.')
      return
    }

    try {
      setError('')
      setLiveResult(null)
      setDialogue(null)
      setAnalysis(null)
      chunksRef.current = []

      if (!promptRequestedAtRef.current) {
        promptRequestedAtRef.current = new Date()
      }
      recordingStartedAtRef.current = new Date()

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const recorder = new MediaRecorder(stream)
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      recorder.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const startedAt = recordingStartedAtRef.current ?? new Date()
        const requestedAt = promptRequestedAtRef.current ?? startedAt
        const audioDuration = Math.max((Date.now() - startedAt.getTime()) / 1000, 1)
        stopStream()
        setDuration(Number(audioDuration.toFixed(1)))
        void runLivePipeline(audioBlob, audioDuration, requestedAt, startedAt)
      }

      recorder.start()
      setIsRecording(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : '마이크 녹음을 시작하지 못했습니다.')
      stopStream()
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
    setIsRecording(false)
  }

  function stopStream() {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }

  async function runLivePipeline(audioBlob: Blob, audioDuration: number, requestedAt: Date, startedAt: Date) {
    setIsLoading(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'meeting-demo.webm')
      formData.append('session_id', 'live-demo-session')
      formData.append('duration_seconds', audioDuration.toFixed(2))
      formData.append('response_requested_at', requestedAt.toISOString())
      formData.append('response_started_at', startedAt.toISOString())

      const result = await postForm<SttPipelineResponse>('/api/stt/pipeline', formData)
      setLiveResult(result)
      setTranscript(result.transcript)
      setAnalysis(result.analysis)
      setDialogue({ analysis: result.analysis, llm: result.llm })
      setLatency(result.analysis.response_latency.seconds ?? 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : '라이브 파이프라인 실행 중 오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
      stopStream()
    }
  }

  async function runAnalysis() {
    setIsLoading(true)
    setError('')
    setDialogue(null)
    try {
      setAnalysis(await postJson<SpeechAnalysis>('/api/speech/analyze', sttPayload))
    } catch (err) {
      setError(err instanceof Error ? err.message : '분석 중 오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  async function sendToLlm() {
    setIsLoading(true)
    setError('')
    try {
      const result = await postJson<DialogueResponse>('/api/dialogue/stt-to-llm', {
        session_id: 'demo-session',
        stt_result: sttPayload,
        child_profile: { name: '마주' },
        conversation_history: [],
      })
      setAnalysis(result.analysis)
      setDialogue(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'LLM 전달 중 오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="appShell">
      <section className="heroBand">
        <div>
          <span>Faster-Whisper baseline</span>
          <h1>MazuTalk STT Demo</h1>
        </div>
        <div className="heroStats">
          <strong>100</strong>
          <span>sample smoke test</span>
        </div>
      </section>

      <section className="workspace">
        <div className="inputPane">
          <div className="sectionHeader">
            <h2>Small 모델 샘플</h2>
            <span>cropped + tuned</span>
          </div>

          <div className="livePanel">
            <div>
              <strong>마이크 파이프라인</strong>
              <span>{isRecording ? '녹음 중' : isLoading ? 'STT 분석 중' : '대기 중'}</span>
            </div>
            <div className="recordActions">
              <button disabled={isLoading || isRecording} onClick={markPromptStart} type="button">
                질문 시작
              </button>
              <button disabled={isLoading || isRecording} onClick={startRecording} type="button">
                녹음 시작
              </button>
              <button disabled={!isRecording} onClick={stopRecording} type="button">
                정지 및 분석
              </button>
            </div>
            {liveResult && (
              <div className="liveSummary">
                <span>{liveResult.stt_model}</span>
                <strong>{liveResult.stt_time_seconds.toFixed(3)}s</strong>
              </div>
            )}
          </div>

          <div className="sampleList">
            {sttSamples.map((sample, index) => (
              <button
                className={sample.id === selectedSampleId ? 'sampleButton active' : 'sampleButton'}
                key={sample.id}
                onClick={() => selectSample(sample.id)}
                type="button"
              >
                <span>#{index + 1}</span>
                <strong>{sample.fileName}</strong>
              </button>
            ))}
          </div>

          <div className="referenceBox">
            <span>정답 라벨</span>
            <p>{selectedSample.reference}</p>
          </div>

          <label>
            STT 결과
            <textarea value={transcript} onChange={(event) => setTranscript(event.target.value)} />
          </label>

          <div className="fieldGrid">
            <label>
              발화 길이
              <input
                min="1"
                type="number"
                value={duration}
                onChange={(event) => setDuration(Number(event.target.value))}
              />
            </label>
            <label>
              응답 지연
              <input
                min="0"
                step="0.5"
                type="number"
                value={latency}
                onChange={(event) => setLatency(Number(event.target.value))}
              />
            </label>
          </div>

          <div className="actions">
            <button disabled={isLoading || !transcript.trim()} onClick={runAnalysis}>
              분석
            </button>
            <button disabled={isLoading || !transcript.trim()} onClick={sendToLlm}>
              LLM 전달
            </button>
          </div>

          {error && <p className="errorText">{error}</p>}
        </div>

        <div className="resultPane">
          <section>
            <h2>모델 비교</h2>
            <div className="comparisonTable">
              <div className="comparisonHeader">
                <span>Model</span>
                <span>CER</span>
                <span>Time</span>
              </div>
              {modelResults.map((result) => (
                <div className="comparisonRow" key={result.model}>
                  <div>
                    <strong>{result.model}</strong>
                    <small>{result.condition}</small>
                  </div>
                  <b>{result.cer.toFixed(4)}</b>
                  <span>{result.avgTime.toFixed(3)}s</span>
                </div>
              ))}
            </div>
          </section>

          <section className="pipelineBox">
            <h2>파이프라인 상태</h2>
            <div className={liveResult ? 'pipelineSteps complete' : 'pipelineSteps'}>
              <span>마이크 입력</span>
              <span>Small STT</span>
              <span>발화 분석</span>
              <span>LLM 전달</span>
            </div>
            {liveResult ? (
              <p>{liveResult.transcript}</p>
            ) : (
              <p className="emptyText">마이크 녹음을 완료하면 실제 음성이 STT 모델과 분석 API를 거쳐 LLM 모듈로 전달됩니다.</p>
            )}
          </section>

          <section>
            <h2>분석 결과</h2>
            {analysis ? (
              <div className="metricGrid">
                <Metric label="발화 속도" value={`${analysis.pace.words_per_minute} WPM`} note={analysis.pace.label} />
                <Metric label="음절 속도" value={`${analysis.pace.syllables_per_second}/s`} note="syllables" />
                <Metric label="반복 점수" value={`${Math.round(analysis.repetition_score * 100)}%`} note={`${analysis.repeated_expressions.length}개`} />
                <Metric label="응답 지연" value={analysis.response_latency.seconds === null ? '-' : `${analysis.response_latency.seconds}s`} note={analysis.response_latency.label} />
              </div>
            ) : (
              <p className="emptyText">분석 버튼을 누르면 발화 속도, 반복 표현, 응답 지연이 표시됩니다.</p>
            )}
          </section>

          {analysis && (
            <section>
              <h2>코칭 포인트</h2>
              <ul>
                {analysis.coaching_tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </section>
          )}

          {dialogue && (
            <section className="dialogueBox">
              <h2>LLM 응답</h2>
              <p>{dialogue.llm.therapist_reply}</p>
              <strong>{dialogue.llm.next_prompt}</strong>
              <small>{dialogue.llm.model_name}</small>
            </section>
          )}
        </div>
      </section>
    </main>
  )
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  )
}
