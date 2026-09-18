# [CEVA 전용] 단위 포맷 함수 (BOX 복수형 BOXES 처리)
def format_unit_ceva(unit, count):
    if not unit: return ""
    u = str(unit).upper().strip()
    mapping = {
        'PLT': 'PLT', 'PALLET': 'PLT', 'PLTS': 'PLT',
        'PKG': 'PKG', 'PKGS': 'PKG',
        'CTN': 'CTN', 'CTNS': 'CTN',
        'BOX': 'BOX', 'BOXES': 'BOX', 'BOXS': 'BOX'
    }
    base = mapping.get(u, u)
    if count > 1:
        if base == 'BOX':
            return 'BOXES'
        return base + "S"
    return base
