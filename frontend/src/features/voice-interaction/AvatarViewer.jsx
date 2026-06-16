// frontend/src/features/voice-interaction/AvatarViewer.jsx
// [역할] VRM 아바타를 Three.js로 화면에 띄우는 컴포넌트
// Zustand에서 볼륨/감정 값을 읽어서 립싱크 + 표정 전환

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader";
import { VRMLoaderPlugin } from "@pixiv/three-vrm";
import useAvatarStore from "../store/avatarStore";
import useLipSync from "./useLipSync";

function AvatarViewer({ avatarUrl = "/김하은.vrm" }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const animFrameRef = useRef(null);
  const vrmRef = useRef(null); // VRM 객체 저장용

  const emotion = useAvatarStore((state) => state.emotion);
  useLipSync(vrmRef); // ← 립싱크 훅 사용

  // ── 감정 변할 때마다 표정 전환 ────────────────
  useEffect(() => {
    if (!vrmRef.current) return;
    const vrm = vrmRef.current;

    // 모든 표정 초기화
    vrm.expressionManager?.setValue("happy", 0);
    vrm.expressionManager?.setValue("sad", 0);
    vrm.expressionManager?.setValue("angry", 0);
    vrm.expressionManager?.setValue("surprised", 0);
    vrm.expressionManager?.setValue("neutral", 0);

    // 현재 감정에 맞는 표정 적용
    const emotionMap = {
      joyful: "happy",
      sad: "sad",
      angry: "angry",
      surprised: "surprised",
      neutral: "neutral",
    };
    const expression = emotionMap[emotion] || "neutral";
    const expressionIntensity = {
      happy: 0.5,
      sad: 0.8,
      angry: 0.8,
      surprised: 0.8,
      neutral: 0,
    };
    vrm.expressionManager?.setValue(expression, expressionIntensity[expression] ?? 1);

  }, [emotion]);

  // ── Three.js 씬 세팅 ──────────────────────────
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
        // VRM 업데이트 (표정/립싱크 반영)
        if (vrmRef.current) {
          vrmRef.current.update(0.016);
        }
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
        vrmRef.current = vrm; // VRM 객체 저장
        sceneRef.current.add(vrm.scene);

        vrm.scene.position.set(0, -0.8, 0);
        vrm.scene.rotation.y = Math.PI;
        vrm.scene.scale.set(1.5, 1.5, 1.5);

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