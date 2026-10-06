// 스튜디오 공용 컨텍스트: 현재 프로세스·단계 이동·새로고침. 각 STEP 화면은 useStudio() 로 받는다.
import { createContext, useContext } from "react";
import type { MutableRefObject } from "react";
import type { Dataset, Gate, ProcessDetail, Reference } from "../types";

export interface GoOptions {
  /** 이동한 단계에서 선택할 데이터셋 (ProcessDataset id) */
  dataset?: number | null;
  /** 강조할 필드·축 이름 (수정 경로의 focus) */
  focus?: string | null;
  /** 위반 수정 왕복: 돌아갈 단계 */
  from?: number | null;
  /** 복귀 배너에 보여 줄 위반 이름 */
  shape?: string | null;
}

export interface StudioValue {
  pid: number;
  step: number;
  detail: ProcessDetail;
  /** 조합에 편입된 데이터셋 (position 순) */
  combo: Dataset[];
  reference: Reference;
  /** 프로세스가 진행 중이고 쓰기 권한이 있을 때만 true. false 면 편집 컨트롤을 비활성화한다. */
  editable: boolean;
  isAdmin: boolean;
  gate: (n: number) => Gate;
  /** 단계 이동. 잠긴 단계면 사유를 토스트로 알리고 이동하지 않는다. */
  go: (step: number, opts?: GoOptions) => void;
  /** 서버 상태를 다시 읽는다 (프로세스 상세와 이 프로세스에 딸린 모든 조회). 변경 요청 뒤에 호출한다. */
  refresh: () => Promise<void>;
  /**
   * 저장하지 않은 변경이 있는 화면이 등록하는 확인 함수. true 를 돌려주면 단계 이동 전에 사용자에게 묻는다.
   * 사용: useEffect(() => { guard.current = () => dirty; return () => { guard.current = null; }; }, [dirty, guard]);
   */
  guard: MutableRefObject<(() => boolean) | null>;
  /** URL 로 전달된 선택 데이터셋·강조 필드 */
  params: { dataset: number | null; focus: string | null; from: number | null; shape: string | null };
}

export const StudioCtx = createContext<StudioValue | null>(null);

export function useStudio(): StudioValue {
  const v = useContext(StudioCtx);
  if (!v) throw new Error("StudioLayout 밖에서 useStudio 를 호출했습니다");
  return v;
}
