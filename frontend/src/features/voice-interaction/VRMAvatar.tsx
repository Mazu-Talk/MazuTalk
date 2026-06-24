// frontend/src/features/voice-interaction/VRMAvatar.tsx
// [역할] VRM 3D 아바타 렌더링 + 립싱크 + 응답 감정 표정 + 장소별 배경.
// - currentEmotion(LLM 응답 감정) → 아바타 표정 (비전 융합 결과의 시각화)
// - lipSyncVolume(TTS 볼륨) → 입 모양. 볼륨 데이터가 없으면 발화 중 합성 입모양.
// - location(시나리오 장소) → three.js 씬 배경(그라데이션, 이미지 있으면 교체)
// 셋업이 실패해도 페이지 전체가 죽지 않도록 try/catch로 격리한다.

import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { VRM, VRMLoaderPlugin } from '@pixiv/three-vrm'
import { useSessionStore } from '@/stores/sessionStore'
import type { AvatarState, Emotion } from '@/types/domain'
import haeunUrl from '@/assets/avatars/김하은.vrm?url'
import hajunUrl from '@/assets/avatars/김하준.vrm?url'

// 캐릭터 → VRM 에셋 URL (Vite가 해시 처리하여 번들)
export const AVATAR_URLS: Record<string, string> = {
  하은: haeunUrl,
  하준: hajunUrl,
}

interface VRMAvatarProps {
  avatarUrl?: string
  /** 시나리오 장소(놀이터/교실/공원 등) → 배경 그라데이션 폴백 */
  location?: string
  /** 시나리오 ID → 장소별 배경 이미지 선택 */
  sceneId?: string
  className?: string
}

// 도메인 AvatarState → VRM 제스처 상태로 축약
type VrmGesture = 'idle' | 'speaking' | 'waiting'
function toGesture(state: AvatarState): VrmGesture {
  if (state === 'speaking') return 'speaking'
  if (state === 'listening' || state === 'thinking') return 'waiting'
  return 'idle'
}

// 응답 감정(Emotion) → VRM 표정 BlendShape (김하은.vrm 프리셋: happy/sad/Surprised/neutral)
const EMOTION_EXPRESSION: Record<Emotion, { name: string; intensity: number }> = {
  happy: { name: 'happy', intensity: 0.5 },
  neutral: { name: 'neutral', intensity: 0 },
  anxious: { name: 'Surprised', intensity: 0.6 },
  confused: { name: 'Surprised', intensity: 0.5 },
  passive: { name: 'neutral', intensity: 0 },
  shy: { name: 'sad', intensity: 0.4 },
  frustrated: { name: 'sad', intensity: 0.7 },
}
const EXPRESSION_NAMES = ['happy', 'sad', 'Surprised', 'neutral']

function applyExpression(vrm: VRM, emotion: Emotion) {
  for (const name of EXPRESSION_NAMES) vrm.expressionManager?.setValue(name, 0)
  const { name, intensity } = EMOTION_EXPRESSION[emotion] ?? EMOTION_EXPRESSION.neutral
  vrm.expressionManager?.setValue(name, intensity)
}

// 장소 키워드 → 배경 팔레트(상단=하늘/벽, 하단=바닥) + 이미지 키
function locationPalette(location = ''): { key: string; top: string; bottom: string } {
  if (location.includes('교실')) return { key: 'classroom', top: '#fde8c8', bottom: '#f0c98b' }
  if (location.includes('모래')) return { key: 'sandbox', top: '#cdeafe', bottom: '#f2dcab' }
  if (location.includes('놀이터')) return { key: 'playground', top: '#bfe3ff', bottom: '#a8e6a1' }
  if (location.includes('공원')) return { key: 'park', top: '#bfe3ff', bottom: '#8fd17a' }
  if (location.includes('유치원')) return { key: 'kindergarten', top: '#ffe0ec', bottom: '#ffc3a0' }
  return { key: 'default', top: '#eef6ff', bottom: '#dfeeff' }
}

function gradientTexture(top: string, bottom: string): THREE.Texture {
  const canvas = document.createElement('canvas')
  canvas.width = 16
  canvas.height = 256
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.Texture()
  const grad = ctx.createLinearGradient(0, 0, 0, 256)
  grad.addColorStop(0, top)
  grad.addColorStop(1, bottom)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 16, 256)
  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

// src/assets/backgrounds/*.{jpg,jpeg,png,webp} 를 빌드 시 수집(있는 것만 번들).
// 키 = 확장자 제외 파일명(slug). 파일을 넣으면 자동으로 잡힌다.
const BG_MODULES = import.meta.glob('../../assets/backgrounds/*.{jpg,jpeg,png,webp}', {
  eager: true,
  import: 'default',
}) as Record<string, string>
const BG_BY_SLUG: Record<string, string> = Object.fromEntries(
  Object.entries(BG_MODULES).map(([path, url]) => [
    path.split('/').pop()!.replace(/\.(jpg|jpeg|png|webp)$/i, ''),
    url,
  ]),
)

// 시나리오 ID → 배경 파일 slug (장소가 겹쳐도 고유하게)
const SCENARIO_BG: Record<string, string> = {
  playground_greeting: 'playground',
  classroom_emotion: 'classroom',
  blocks_help: 'classroom_playtime',
  sandbox_conflict: 'sandbox',
  park_joining_play: 'park',
  goodbye_friend: 'kindergarten',
}

/** 시나리오/장소에 맞는 배경 이미지 URL (없으면 null → 그라데이션 폴백) */
function backgroundUrlFor(sceneId: string | undefined, paletteKey: string): string | null {
  const slug = (sceneId && SCENARIO_BG[sceneId]) || paletteKey
  return BG_BY_SLUG[slug] ?? BG_BY_SLUG[paletteKey] ?? BG_BY_SLUG.default ?? null
}

export function VRMAvatar({ avatarUrl = haeunUrl, location, sceneId, className }: VRMAvatarProps) {
  const mountRef = useRef<HTMLDivElement>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const vrmRef = useRef<VRM | null>(null)
  const timeRef = useRef(0)
  const blinkTimerRef = useRef(0)
  const [setupError, setSetupError] = useState<string | null>(null)

  // 응답 감정 변경 시 표정 전환
  const currentEmotion = useSessionStore((s) => s.currentEmotion)
  useEffect(() => {
    if (vrmRef.current) applyExpression(vrmRef.current, currentEmotion)
  }, [currentEmotion])

  // Three.js 씬 + 애니메이션 루프 (셋업 실패해도 페이지는 유지)
  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    try {
      const width = mount.clientWidth || 320
      const height = mount.clientHeight || 480

      const scene = new THREE.Scene()
      sceneRef.current = scene

      // 장소별 배경: 즉시 그라데이션 → src/assets/backgrounds 이미지가 있으면 교체
      const palette = locationPalette(location)
      scene.background = gradientTexture(palette.top, palette.bottom)
      const bgUrl = backgroundUrlFor(sceneId, palette.key)
      if (bgUrl) {
        new THREE.TextureLoader().load(bgUrl, (tex) => {
          tex.colorSpace = THREE.SRGBColorSpace
          if (sceneRef.current) sceneRef.current.background = tex
        })
      }

      const camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 20)
      camera.position.set(0, 1.2, 3)
      camera.lookAt(0, 1.0, 0)

      const renderer = new THREE.WebGLRenderer({ antialias: true })
      renderer.setSize(width, height)
      renderer.setPixelRatio(window.devicePixelRatio)
      mount.appendChild(renderer.domElement)
      rendererRef.current = renderer

      const dirLight = new THREE.DirectionalLight(0xffffff, 1)
      dirLight.position.set(1, 2, 3)
      scene.add(dirLight)
      scene.add(new THREE.AmbientLight(0xffffff, 0.6))

      const loader = new GLTFLoader()
      loader.register((parser) => new VRMLoaderPlugin(parser))
      loader.load(
        avatarUrl,
        (gltf: GLTF) => {
          const vrm = gltf.userData.vrm as VRM
          vrmRef.current = vrm
          scene.add(vrm.scene)
          vrm.scene.position.set(0, -0.8, 0)
          vrm.scene.rotation.y = Math.PI // VRM0 정면 보정
          vrm.scene.scale.set(1.5, 1.5, 1.5)
          applyExpression(vrm, useSessionStore.getState().currentEmotion)
          useSessionStore.getState().setLipSyncVolume(0)
        },
        undefined,
        (error) => console.error('VRM 아바타 로드 실패:', error),
      )

      const animate = () => {
        animFrameRef.current = requestAnimationFrame(animate)
        const vrm = vrmRef.current
        if (!vrm) {
          renderer.render(scene, camera)
          return
        }

        timeRef.current += 0.016
        const t = timeRef.current
        const { lipSyncVolume, avatarState, phase } = useSessionStore.getState()
        const gesture = toGesture(avatarState)

        // 립싱크: 실제 볼륨 우선, 발화 중 볼륨 데이터가 없으면 합성 입모양
        let mouth = Math.min(Math.pow(Math.max(lipSyncVolume, 0), 1.5) * 2.5, 1)
        if (phase === 'speaking' && lipSyncVolume < 0.03) {
          mouth = (Math.sin(t * 14) * 0.5 + 0.5) * 0.55
        }
        vrm.expressionManager?.setValue('aa', mouth)

        // 숨쉬기
        const chest = vrm.humanoid?.getNormalizedBoneNode('chest')
        if (chest) chest.rotation.x = Math.sin(t * 1.2) * 0.03

        // 눈 깜빡임 (3~5초 랜덤)
        blinkTimerRef.current += 0.016
        const blinkInterval = 3.5 + Math.sin(t * 0.3) * 1.5
        if (blinkTimerRef.current >= blinkInterval) {
          blinkTimerRef.current = 0
          vrm.expressionManager?.setValue('blink', 1)
          setTimeout(() => vrmRef.current?.expressionManager?.setValue('blink', 0), 150)
        }

        // 팔 내리기 (공통)
        const leftArm = vrm.humanoid?.getNormalizedBoneNode('leftUpperArm')
        if (leftArm) leftArm.rotation.z = THREE.MathUtils.lerp(leftArm.rotation.z, 1.2 + Math.sin(t * 0.8) * 0.03, 0.05)
        const rightArm = vrm.humanoid?.getNormalizedBoneNode('rightUpperArm')
        if (rightArm) rightArm.rotation.z = THREE.MathUtils.lerp(rightArm.rotation.z, -1.2 - Math.sin(t * 0.8) * 0.03, 0.05)

        // 상태별 고개
        const head = vrm.humanoid?.getNormalizedBoneNode('head')
        if (head) {
          if (gesture === 'idle') head.rotation.y = Math.sin(t * 0.5) * 0.05
          else if (gesture === 'speaking') head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, 0, 0.05)
          else head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, 0.1, 0.05) // waiting: 살짝 갸웃
        }

        vrm.update(0.016)
        renderer.render(scene, camera)
      }
      animate()
    } catch (err) {
      console.error('VRMAvatar 셋업 실패:', err)
      setSetupError((err as Error).message)
    }

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      const renderer = rendererRef.current
      if (renderer) {
        renderer.dispose()
        if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
      }
      vrmRef.current = null
      rendererRef.current = null
      sceneRef.current = null
    }
  }, [avatarUrl, location, sceneId])

  return (
    <div ref={mountRef} className={className} style={{ position: 'relative', width: '100%', height: '100%' }}>
      {setupError && (
        <div className="absolute inset-0 grid place-items-center p-3 text-center text-xs text-red-500">
          아바타를 표시할 수 없어요
          <br />({setupError})
        </div>
      )}
    </div>
  )
}

export default VRMAvatar
