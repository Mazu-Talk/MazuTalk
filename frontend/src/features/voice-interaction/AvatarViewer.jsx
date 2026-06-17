// frontend/src/features/voice-interaction/AvatarViewer.jsx
// [역할] VRM 아바타 렌더링 + 립싱크 + 감정 표현 + 상태별 인터랙션 통합 컴포넌트

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader";
import { VRMLoaderPlugin } from "@pixiv/three-vrm";
import useAvatarStore from "../store/avatarStore";

function AvatarViewer({ avatarUrl = "/김하은.vrm" }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const animFrameRef = useRef(null);
  const vrmRef = useRef(null);       // VRM 객체 저장용
  const timeRef = useRef(0);         // 애니메이션 시간 추적
  const blinkTimerRef = useRef(0);   // 눈 깜빡임 타이머
  const greetTimerRef = useRef(0);   // 인사 애니메이션 타이머

  // ── 감정 변할 때마다 표정 전환 ────────────────────────────────────
  const emotion = useAvatarStore((state) => state.emotion);

  useEffect(() => {
    if (!vrmRef.current) return;
    const vrm = vrmRef.current;

    // 모든 표정 초기화 후 현재 감정 표정 적용
    vrm.expressionManager?.setValue("happy", 0);
    vrm.expressionManager?.setValue("sad", 0);
    vrm.expressionManager?.setValue("Surprised", 0);
    vrm.expressionManager?.setValue("neutral", 0);

    const emotionMap = {
      joyful: "happy",
      sad: "sad",
      surprised: "Surprised",
      neutral: "neutral",
    };
    const expression = emotionMap[emotion] || "neutral";

    // 감정별 표정 강도 (happy는 입이 너무 벌어지지 않게 0.5로 설정)
    const expressionIntensity = {
      happy: 0.5,
      sad: 0.8,
      relaxed: 0.8,
      surprised: 0.8,
      neutral: 0,
    };
    vrm.expressionManager?.setValue(expression, expressionIntensity[expression] ?? 1);

  }, [emotion]);

  // ── Three.js 씬 세팅 + 통합 애니메이션 루프 ──────────────────────
  useEffect(() => {
    if (sceneRef.current) {
      while (sceneRef.current.children.length > 0) {
        sceneRef.current.remove(sceneRef.current.children[0]);
      }
    }

    if (!rendererRef.current) {
      const width = mountRef.current.clientWidth || 400;
      const height = mountRef.current.clientHeight || 600;

      sceneRef.current = new THREE.Scene();
      sceneRef.current.background = new THREE.Color(0xf0f0f0);

      cameraRef.current = new THREE.PerspectiveCamera(30, width / height, 0.1, 20);
      cameraRef.current.position.set(0, 1.2, 3);
      cameraRef.current.lookAt(0, 1.0, 0);

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(width, height);
      renderer.setPixelRatio(window.devicePixelRatio);
      mountRef.current.appendChild(renderer.domElement);
      rendererRef.current = renderer;

      const animate = () => {
        animFrameRef.current = requestAnimationFrame(animate);
        const vrm = vrmRef.current;
        if (!vrm) {
          rendererRef.current.render(sceneRef.current, cameraRef.current);
          return;
        }

        timeRef.current += 0.016;
        const t = timeRef.current;

        // Zustand에서 직접 읽기 → 루프 재실행 없이 최신 상태 반영
        const { volume, avatarState } = useAvatarStore.getState();

        // ── 립싱크: 볼륨 → 입 BlendShape ──────────────────────────
        // 볼륨에 제곱 적용 → 작은 값은 더 작게, 큰 값은 더 크게
        const shaped = Math.pow(volume, 1.5);
        vrm.expressionManager?.setValue("aa", Math.min(shaped * 2.5, 1));

        // ── 공통 애니메이션 (모든 상태에서 항상 적용) ──────────────

        // 숨쉬기: 가슴 본을 sin 함수로 위아래 반복
        const chest = vrm.humanoid?.getNormalizedBoneNode("chest");
        if (chest) {
          chest.rotation.x = Math.sin(t * 1.2) * 0.03;
        }

        // 눈 깜빡임: 3~5초 사이 랜덤 간격으로 한 번씩
        blinkTimerRef.current += 0.016;
        const blinkInterval = 3.5 + Math.sin(t * 0.3) * 1.5;
        if (blinkTimerRef.current >= blinkInterval) {
          blinkTimerRef.current = 0;
          vrm.expressionManager?.setValue("blink", 1); // 눈 감기
          setTimeout(() => {
            if (vrm) vrm.expressionManager?.setValue("blink", 0); // 0.15초 후 눈 뜨기
          }, 150);
        }

        // ── 상태별 애니메이션 ───────────────────────────────────────

        // 대기 상태: 팔 내리기 + 고개 살짝 좌우로
        if (avatarState === "idle") {
          const leftArm = vrm.humanoid?.getNormalizedBoneNode("leftUpperArm");
          if (leftArm) {
            leftArm.rotation.z = THREE.MathUtils.lerp(
              leftArm.rotation.z, 1.2 + Math.sin(t * 0.8) * 0.03, 0.05
            );
          }
          const rightArm = vrm.humanoid?.getNormalizedBoneNode("rightUpperArm");
          if (rightArm) {
            rightArm.rotation.z = THREE.MathUtils.lerp(
              rightArm.rotation.z, -1.2 - Math.sin(t * 0.8) * 0.03, 0.05
            );
          }
          const head = vrm.humanoid?.getNormalizedBoneNode("head");
          if (head) {
            head.rotation.y = Math.sin(t * 0.5) * 0.05;
          }
        }

        // 말하는 상태: 팔 내리기 + 고개 정면 고정
        if (avatarState === "speaking") {
          const leftArm = vrm.humanoid?.getNormalizedBoneNode("leftUpperArm");
          if (leftArm) {
            leftArm.rotation.z = THREE.MathUtils.lerp(leftArm.rotation.z, 1.2 + Math.sin(t * 0.8) * 0.03, 0.05);
          }
          const rightArm = vrm.humanoid?.getNormalizedBoneNode("rightUpperArm");
          if (rightArm) {
            rightArm.rotation.z = THREE.MathUtils.lerp(rightArm.rotation.z, -1.2 - Math.sin(t * 0.8) * 0.03, 0.05);
          }
          const head = vrm.humanoid?.getNormalizedBoneNode("head");
          if (head) {
            head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, 0, 0.05);
          }
        }

        // 기다리는 상태: 팔 내리기 + 고개 살짝 기울이기
        if (avatarState === "waiting") {
          const leftArm = vrm.humanoid?.getNormalizedBoneNode("leftUpperArm");
          if (leftArm) {
            leftArm.rotation.z = THREE.MathUtils.lerp(leftArm.rotation.z, 1.2 + Math.sin(t * 0.8) * 0.03, 0.05);
          }
          const rightArm = vrm.humanoid?.getNormalizedBoneNode("rightUpperArm");
          if (rightArm) {
            rightArm.rotation.z = THREE.MathUtils.lerp(rightArm.rotation.z, -1.2 - Math.sin(t * 0.8) * 0.03, 0.05);
          }
          const head = vrm.humanoid?.getNormalizedBoneNode("head");
          if (head) {
            head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, 0.1, 0.05);
          }
        }

        // 인사 상태: 위팔 45도 고정 + 팔꿈치 흔들기 + 손바닥 정면
        if (avatarState === "greeting") {
          greetTimerRef.current += 0.016;

          // 위팔: 45도(0.785 라디안)로 고정
          const rightUpperArm = vrm.humanoid?.getNormalizedBoneNode("rightUpperArm");
          if (rightUpperArm) {
            rightUpperArm.rotation.z = THREE.MathUtils.lerp(
              rightUpperArm.rotation.z, -0.785, 0.05
            );
          }

          // 아랫팔: sin 함수로 위아래 흔들기 (* 2 = 속도, * 0.6 = 폭)
          const rightLowerArm = vrm.humanoid?.getNormalizedBoneNode("rightLowerArm");
          if (rightLowerArm) {
            rightLowerArm.rotation.z = 2.5 - Math.abs(Math.sin(greetTimerRef.current * 2)) * 0.6;
          }

          // 손목: x축 회전으로 손바닥 정면으로
          const rightHand = vrm.humanoid?.getNormalizedBoneNode("rightHand");
          if (rightHand) {
            rightHand.rotation.x = THREE.MathUtils.lerp(rightHand.rotation.x, 2.0, 1.0);
          }

        } else {
          greetTimerRef.current = 0;

          // 인사 끝나면 팔꿈치/손목 원위치로 부드럽게 복귀
          const rightLowerArm = vrm.humanoid?.getNormalizedBoneNode("rightLowerArm");
          if (rightLowerArm) {
            rightLowerArm.rotation.z = THREE.MathUtils.lerp(rightLowerArm.rotation.z, 0, 0.05);
          }
          const rightHand = vrm.humanoid?.getNormalizedBoneNode("rightHand");
          if (rightHand) {
            rightHand.rotation.x = THREE.MathUtils.lerp(rightHand.rotation.x, 0, 0.05);
          }
        }

        // VRM 업데이트 → 한 번만 호출
        vrm.update(0.016);
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      };
      animate();
    }

    const dirLight = new THREE.DirectionalLight(0xffffff, 1);
    dirLight.position.set(1, 2, 3);
    sceneRef.current.add(dirLight);
    sceneRef.current.add(new THREE.AmbientLight(0xffffff, 0.6));

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      avatarUrl,
      (gltf) => {
        const vrm = gltf.userData.vrm;
        vrmRef.current = vrm;
        sceneRef.current.add(vrm.scene);

        vrm.scene.position.set(0, -0.8, 0);
        vrm.scene.rotation.y = Math.PI;
        vrm.scene.scale.set(1.5, 1.5, 1.5);

        // VRM 로드 완료 시 idle 상태로 초기화
        useAvatarStore.getState().setAvatarState("idle");
        console.log("아바타 로드 완료!");
      },
      (progress) => {
        console.log("로딩 중...", (progress.loaded / progress.total) * 100, "%");
      },
      (error) => {
        console.error("아바타 로드 실패:", error);
      }
    );

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
      if (rendererRef.current && mountRef.current) {
        mountRef.current.removeChild(rendererRef.current.domElement);
        rendererRef.current.dispose();
        rendererRef.current = null;
      }
    };
  }, [avatarUrl]);

  return (
    <div
      ref={mountRef}
      style={{ width: "100%", height: "600px" }}
    />
  );
}

export default AvatarViewer;