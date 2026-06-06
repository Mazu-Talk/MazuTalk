// frontend/src/features/voice-interaction/useLipSync.js
// [역할] 볼륨 값 → VRM 입 BlendShape 변환 로직
// AvatarViewer.jsx에서 import해서 사용

import { useEffect } from "react";
import useAvatarStore from "../store/avatarStore";

function useLipSync(vrmRef) {
  const volume = useAvatarStore((state) => state.volume);

  useEffect(() => {
    if (!vrmRef.current) return;
    const vrm = vrmRef.current;

    // 볼륨 값으로 입 열림 조절
    // 볼륨에 제곱 적용 → 작은 값은 더 작게, 큰 값은 더 크게
    const shaped = Math.pow(volume, 1.5); // 1.5 ~ 2.0 사이로 조절
    
    // volume: 0~1 → BlendShape "aa": 0~1
    vrm.expressionManager?.setValue("aa", Math.min(shaped * 2.5, 1));

  }, [volume]);
}

export default useLipSync;