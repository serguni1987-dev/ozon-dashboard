# pnl_format.py — оформление листа P&L (50 строк). Значения не трогает.
import os, gspread
from google.oauth2.service_account import Credentials
import sync_pnl

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CRED = os.path.join(APP_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

def rgb(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2],16)/255, "green": int(h[2:4],16)/255, "blue": int(h[4:6],16)/255}

WHITE=rgb("FFFFFF"); BLACK=rgb("000000"); GREY_TXT=rgb("666666")
NAVY=rgb("2F5496"); HEAD_FG=rgb("FFFFFF"); YEAR_BG=rgb("D9E2F3")
QUART_BG=rgb("E4DFEC"); GREEN_BG=rgb("C6E0B4"); GREEN_FG=rgb("1F4E1F")
RED_TXT=rgb("833C0C"); ORANGE_BG=rgb("FCE4D6"); RED_BG=rgb("F4CCCC")
RED_FG=rgb("7F0000"); BORDER=rgb("BFBFBF")

def grid(sid,r0,r1,c0=0,c1=19):
    return {"sheetId":sid,"startRowIndex":r0,"endRowIndex":r1,
            "startColumnIndex":c0,"endColumnIndex":c1}

def cell(bg=None,fg=None,bold=False,italic=False,size=11,align=None):
    cf={"textFormat":{"bold":bold,"italic":italic,"fontSize":size}}
    if fg: cf["textFormat"]["foregroundColor"]=fg
    if bg: cf["backgroundColor"]=bg
    if align: cf["horizontalAlignment"]=align
    return cf

def build_requests(sid, net_val):
    reqs=[]; N=50
    # заголовок
    reqs.append({"unmergeCells":{"range":grid(sid,0,1)}})
    reqs.append({"mergeCells":{"range":grid(sid,0,1),"mergeType":"MERGE_ALL"}})
    reqs.append({"repeatCell":{"range":grid(sid,0,1),
        "cell":{"userEnteredFormat":cell(bg=NAVY,fg=HEAD_FG,bold=True,size=16,align="CENTER")},
        "fields":"userEnteredFormat"}})
    reqs.append({"updateDimensionProperties":{
        "range":{"sheetId":sid,"dimension":"ROWS","startIndex":0,"endIndex":1},
        "properties":{"pixelSize":45},"fields":"pixelSize"}})
    # шапка
    reqs.append({"repeatCell":{"range":grid(sid,1,2),
        "cell":{"userEnteredFormat":cell(bg=NAVY,fg=HEAD_FG,bold=True,size=11,align="CENTER")},
        "fields":"userEnteredFormat"}})
    reqs.append({"updateDimensionProperties":{
        "range":{"sheetId":sid,"dimension":"ROWS","startIndex":1,"endIndex":2},
        "properties":{"pixelSize":36},"fields":"pixelSize"}})
    # колонки
    reqs.append({"repeatCell":{"range":grid(sid,2,N,1,2),
        "cell":{"userEnteredFormat":{"backgroundColor":YEAR_BG}},
        "fields":"userEnteredFormat.backgroundColor"}})
    reqs.append({"repeatCell":{"range":grid(sid,2,N,14,18),
        "cell":{"userEnteredFormat":{"backgroundColor":QUART_BG}},
        "fields":"userEnteredFormat.backgroundColor"}})
    # секции
    for r,(bg,fg) in {8:(GREEN_BG,GREEN_FG),14:(ORANGE_BG,RED_TXT),
                      34:(GREEN_BG,GREEN_FG),42:(GREEN_BG,GREEN_FG),
                      44:(None,RED_TXT),49:(GREEN_BG,GREEN_FG),
                      50:(GREEN_BG,GREEN_FG)}.items():
        reqs.append({"repeatCell":{"range":grid(sid,r-1,r),
            "cell":{"userEnteredFormat":cell(bg=bg,fg=fg,bold=True,size=11)},
            "fields":"userEnteredFormat"}})
    # ЧИСТАЯ
    if net_val>=0: bg,fg=GREEN_BG,GREEN_FG
    else: bg,fg=RED_BG,RED_FG
    reqs.append({"repeatCell":{"range":grid(sid,45,46),
        "cell":{"userEnteredFormat":cell(bg=bg,fg=fg,bold=True,size=13)},
        "fields":"userEnteredFormat"}})
    # Себестоимость
    reqs.append({"repeatCell":{"range":grid(sid,31,32),
        "cell":{"userEnteredFormat":cell(fg=RED_TXT,bold=True,size=11)},
        "fields":"userEnteredFormat"}})
    # родители без фона
    for r in (16,21,36):
        reqs.append({"repeatCell":{"range":grid(sid,r-1,r),
            "cell":{"userEnteredFormat":cell(bg=WHITE,fg=BLACK,bold=True,size=11)},
            "fields":"userEnteredFormat"}})
    # дети — серые italic
    for r in (17,18,19,20,22,23,24,25,26,37,38,39,40):
        reqs.append({"repeatCell":{"range":grid(sid,r-1,r),
            "cell":{"userEnteredFormat":cell(bg=WHITE,fg=GREY_TXT,italic=True,size=10)},
            "fields":"userEnteredFormat"}})
    # справочные + хвост
    for r in (3,4,5,6,47,48):
        reqs.append({"repeatCell":{"range":grid(sid,r-1,r),
            "cell":{"userEnteredFormat":cell(bg=WHITE,fg=GREY_TXT,italic=True,size=10)},
            "fields":"userEnteredFormat"}})
    # обычные
    for r in (9,10,11,12,15,27,28,29,30):
        reqs.append({"repeatCell":{"range":grid(sid,r-1,r),
            "cell":{"userEnteredFormat":cell(bg=WHITE,fg=BLACK,bold=False,size=11)},
            "fields":"userEnteredFormat"}})
    # пустые
    for r in (7,13,31,33,35,41,43,45):
        reqs.append({"repeatCell":{"range":grid(sid,r-1,r),
            "cell":{"userEnteredFormat":{"backgroundColor":WHITE}},
            "fields":"userEnteredFormat.backgroundColor"}})
    # выравнивание
    reqs.append({"repeatCell":{"range":grid(sid,2,N,0,1),
        "cell":{"userEnteredFormat":{"horizontalAlignment":"LEFT"}},
        "fields":"userEnteredFormat.horizontalAlignment"}})
    reqs.append({"repeatCell":{"range":grid(sid,2,N,1,19),
        "cell":{"userEnteredFormat":{"horizontalAlignment":"RIGHT"}},
        "fields":"userEnteredFormat.horizontalAlignment"}})
    # числа
    NUM='# ##0.00;-# ##0.00'
    reqs.append({"repeatCell":{"range":grid(sid,2,N,1,19),
        "cell":{"userEnteredFormat":{"numberFormat":{"type":"NUMBER","pattern":NUM}}},
        "fields":"userEnteredFormat.numberFormat"}})
    reqs.append({"repeatCell":{"range":grid(sid,46,47,1,19),
        "cell":{"userEnteredFormat":{"numberFormat":{"type":"NUMBER","pattern":'0.00" %"'}}},
        "fields":"userEnteredFormat.numberFormat"}})
    # ширины
    reqs.append({"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS","startIndex":0,"endIndex":1},
        "properties":{"pixelSize":320},"fields":"pixelSize"}})
    reqs.append({"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS","startIndex":1,"endIndex":2},
        "properties":{"pixelSize":120},"fields":"pixelSize"}})
    for i in range(2,19):
        reqs.append({"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS","startIndex":i,"endIndex":i+1},
            "properties":{"pixelSize":85},"fields":"pixelSize"}})
    # границы
    reqs.append({"updateBorders":{"range":grid(sid,0,1),
        "bottom":{"style":"SOLID_THICK","color":NAVY}}})
    for r in (8,14,16,21,32,34,36,42,44,46,49,50):
        reqs.append({"updateBorders":{"range":grid(sid,r-1,r),
            "top":{"style":"SOLID","color":BORDER},
            "bottom":{"style":"SOLID","color":BORDER}}})
    return reqs

def apply_notes(ws):
    NOTES={
        3:"Количество заказов за период. Справочно.",
        4:"Баллы за скидки, начисленные Ozon. Справочно.",
        5:"Сумма соответствует «Всего к начислению» из Отчёта.",
        6:"Сумма из Акта сверки Ozon.",
        8:"База 100% для расчёта процентов.",
        9:"Продажи минус возвраты. Основной доход.",
        10:"Компенсация от Ozon за скидки продавца.",
        11:"Соинвестиции Ozon в продвижение товара.",
        12:"Прочие компенсации от Ozon.",
        14:"Сумма всех переменных расходов.",
        15:"Комиссия Ozon за вычетом возвратов.",
        16:"Сумма строк 17–20.",
        17:"Logistic + SupplyInbound. Логистика отправлений.",
        18:"ReturnFlowLogistic + SellerReturns + PickUpPointReturnAcceptance.",
        19:"LastMileCourier + DeliveryToHandoverPlaceByOzon.",
        20:"CrossDock, Drop-Off, PackageCost, PackingFee и др.",
        21:"Сумма строк 22–26.",
        22:"PayPerClick — реклама в Ozon.",
        23:"Promotion — продвижение товаров.",
        24:"StarsMembership — подписка Звёзды.",
        25:"BrandCommission — брендовая комиссия.",
        26:"PointsForReviews + AcceleratedReviewCollection.",
        27:"Acquiring, EarlyPayment, FlexiblePayments, Installment.",
        28:"Placements, StockInsurance.",
        29:"DefectRate, Disposal, PremiumCashback, PremiumSubscription, штрафы.",
        30:"Cancellation, ClientReturn, PartialReturn.",
        32:"cost_price × количество.",
        34:"= Доходы − Прямые расходы − Себестоимость.",
        36:"Сумма строк 37–40. Автоматически.",
        37:"Зарплата, налоги с ФОТ. Ручной ввод по месяцам C:N.",
        38:"Аренда, связь, канцелярия. Ручной ввод.",
        39:"Реклама вне Ozon, упаковка. Ручной ввод.",
        40:"Прочие операционные расходы. Ручной ввод.",
        42:"= Валовая прибыль − Операционные расходы.",
        44:"База расчёта: уточнить у бухгалтера.",
        46:"= EBITDA − Налоги. Зелёный — плюс, красный — минус.",
        47:"= Чистая прибыль / Себестоимость × 100%.",
        48:"Выплачено за период.",
        49:"= Чистая прибыль − Дивиденды.",
        50:"Сумма по всем месяцам на текущий момент.",
    }
    sid=ws.id
    reqs=[{"updateCells":{"range":grid(sid,r-1,r,0,1),
        "rows":[{"values":[{"note":t}]}],"fields":"note"}} for r,t in NOTES.items()]
    for i in range(0,len(reqs),50):
        ws.spreadsheet.batch_update({"requests":reqs[i:i+50]})
    print(f"[OK] Примечаний: {len(reqs)}")

def main():
    creds=Credentials.from_service_account_file(CRED,scopes=SCOPES)
    gc=gspread.authorize(creds)
    sh=gc.open_by_key(sync_pnl.SHEET_ID)
    ws=sh.worksheet("P&L"); sid=ws.id
    net_val=0.0
    try:
        v=ws.acell("B46").value
        if v:
            net_val=float(str(v).replace(" ","").replace("\xa0","").replace(",",".").replace("₽","").replace("%","").strip())
    except Exception: pass
    print(f"Чистая прибыль (B46) = {net_val}")
    reqs=build_requests(sid,net_val)
    total=0
    for i in range(0,len(reqs),50):
        chunk=reqs[i:i+50]
        try:
            sh.batch_update({"requests":chunk}); total+=len(chunk)
        except Exception as e:
            print(f"[FAIL] чанк {i//50}: {e}")
    print(f"[OK] Стилей: {total}/{len(reqs)}")
    try:
        sh.batch_update({"requests":[{"updateSheetProperties":{
            "properties":{"sheetId":sid,"gridProperties":{"frozenRowCount":2}},
            "fields":"gridProperties.frozenRowCount"}}]})
        print("[OK] Закреплены строки 1-2")
    except Exception as e:
        print(f"[i] Freeze: {e}")
    apply_notes(ws); print("Готово.")

if __name__=="__main__":
    main()