"""테스트용 표본 파일 생성기."""
import io


def road_xlsx() -> bytes:
    """제목 행 2줄이 위에 붙은 공공 엑셀 양식을 흉내 낸 도로 목록."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "도로목록"
    ws.append(["도로 공간정보 목록 (2026년 8월 기준)"])
    ws.append([])
    ws.append(["LINK_ID", "도로명", "시군구코드", "경도", "위도", "연장(m)", "기준일자"])
    for i in range(1, 201):
        ws.append([f"L{i:05d}", f"테스트로{i}", "11110" if i % 2 else "41135", 126.9 + i / 10000, 37.5 + i / 10000,
                   100 + i, f"2026-08-{(i % 28) + 1:02d}"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def accident_csv() -> bytes:
    """cp949 인코딩 · 시간 포맷 혼재 · 결측 표기 혼재 · 개인정보 의심 컬럼이 있는 사고 목록."""
    lines = ["사고번호,발생일시,도로링크ID,사고주소,차량번호,사망자수,비고"]
    for i in range(1, 151):
        link = f"L{(i % 120) + 1:05d}" if i % 10 else f"X{i:05d}"
        when = f"2026-07-{(i % 28) + 1:02d} 08:{i % 60:02d}:00" if i % 3 else f"2026{7:02d}{(i % 28) + 1:02d}"
        note = ["", "-", "null", "정상"][i % 4]
        lines.append(f"A{i:06d},{when},{link},서울특별시 종로구 세종대로 {i},{12 + i % 80}가{1000 + i},{i % 3},{note}")
    return "\n".join(lines).encode("cp949")
