import ccxt, asyncio, time, numpy as np, os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
load_dotenv()

# === CONFIG SEGURA - AGORA SOFISTICADA ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINGX_API_KEY = os.getenv("BINGX_API_KEY")
BINGX_SECRET = os.getenv("BINGX_SECRET")

if not TELEGRAM_TOKEN or not BINGX_API_KEY:
    print("ERRO: Tokens não encontrados na Render!")

bingx = ccxt.bingx({
    'apiKey': BINGX_API_KEY,
    'secret': BINGX_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

banca = 4.0
rodando = False

# === FILTRO FIRME - TEU ORIGINAL MANTIDO ===
def criterio_forte():
    blacklist = ["USDC", "DAI", "TUSD", "FDUSD", "BULL", "BEAR", "UP", "DOWN", "USDE"]
    try:
        tickers = bingx.fetch_tickers()
        candidatos = []
        for simbolo, dados in tickers.items():
            if "/USDT" not in simbolo: continue
            if any(x in simbolo for x in blacklist): continue
            if not dados['percentage'] or not dados['quoteVolume']: continue
            vol = dados['percentage']
            volume = dados['quoteVolume']
            if volume < 5000000: continue
            if not (5 <= vol <= 40): continue
            try:
                velas = bingx.fetch_ohlcv(simbolo, '15m', limit=60)
                fechamentos = [c[4] for c in velas]
                if len(fechamentos) < 50: continue
                ema20 = np.mean(fechamentos[-20:])
                ema50 = np.mean(fechamentos[-50:])
                preco = fechamentos[-1]
                if not (preco > ema20 > ema50): continue
                ganhos = [max(0, fechamentos[i]-fechamentos[i-1]) for i in range(1,len(fechamentos))]
                perdas = [max(0, fechamentos[i-1]-fechamentos[i]) for i in range(1,len(fechamentos))]
                if np.mean(perdas[-14:]) == 0: continue
                rs = np.mean(ganhos[-14:]) / np.mean(perdas[-14:])
                rsi = 100 - (100 / (1+rs))
                if not (55 <= rsi <= 75): continue
                score = vol * 0.5 + (volume/1000000)*0.3 + rsi*0.2
                candidatos.append((simbolo, score, vol, rsi))
            except:
                continue
        candidatos.sort(key=lambda x: x[1], reverse=True)
        if len(candidatos) >= 2:
            return candidatos[0][0], candidatos[1][0]
        elif len(candidatos) == 1:
            return candidatos[0][0], "PEPE/USDT"
        else:
            return "PEPE/USDT", "WIF/USDT"
    except:
        return "PEPE/USDT", "WIF/USDT"

# === BOT DUPLO 2:2 ===
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global rodando, banca
    rodando = True
    await update.message.reply_text(f"🚀 BOT BBD02 LIGADO\nBanca: ${banca} (2:2)\nFiltro firme ON")

    while rodando:
        try:
            moeda1, moeda2 = criterio_forte()
            if moeda1 == moeda2: moeda2 = "BONK/USDT"
            banca_par = banca / 2
            p1 = bingx.fetch_ticker(moeda1)['last']
            p2 = bingx.fetch_ticker(moeda2)['last']
            qtd1 = banca_par / p1
            qtd2 = banca_par / p2
            bingx.create_market_buy_order(moeda1, qtd1)
            bingx.create_market_buy_order(moeda2, qtd2)
            await update.message.reply_text(f"📥 COMPREI 2:2\n1) {moeda1} ${banca_par:.2f}\n2) {moeda2} ${banca_par:.2f}")
            entrada1, entrada2 = p1, p2
            vendeu1, vendeu2 = False, False
            lucro1, lucro2 = 0, 0
            while rodando and (not vendeu1 or not vendeu2):
                try:
                    if not vendeu1:
                        atual1 = bingx.fetch_ticker(moeda1)['last']
                        pnl1 = (atual1 - entrada1) / entrada1
                        if pnl1 >= 0.25 or pnl1 <= -0.12:
                            bingx.create_market_sell_order(moeda1, qtd1)
                            lucro1 = banca_par * pnl1
                            vendeu1 = True
                            await update.message.reply_text(f"{'✅' if pnl1>0 else '🛑'} {moeda1} {pnl1*100:.1f}%")
                    if not vendeu2:
                        atual2 = bingx.fetch_ticker(moeda2)['last']
                        pnl2 = (atual2 - entrada2) / entrada2
                        if pnl2 >= 0.25 or pnl2 <= -0.11:
                            bingx.create_market_sell_order(moeda2, qtd2)
                            lucro2 = banca_par * pnl2
                            vendeu2 = True
                            await update.message.reply_text(f"{'✅' if pnl2>0 else '🛑'} {moeda2} {pnl2*100:.1f}%")
                    await asyncio.sleep(5)
                except:
                    await asyncio.sleep(2)
                    continue
            banca += lucro1 + lucro2
            await update.message.reply_text(f"🔄 Ciclo fechado. Banca agora: ${banca:.2f}\nBuscando próximas 2...")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Erro mas vou reiniciar: {e}")
            await asyncio.sleep(5)

async def parar(update, context):
    global rodando
    rodando = False
    await update.message.reply_text(f"⏸️ Parado. Banca: ${banca:.2f}")

async def set_banca(update, context):
    global banca
    try:
        banca = float(context.args[0])
        await update.message.reply_text(f"💰 Banca = ${banca}")
    except:
        await update.message.reply_text("Use: /banca 4")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("iniciar", iniciar))
app.add_handler(CommandHandler("parar", parar))
app.add_handler(CommandHandler("banca", set_banca))
print("Bot BBD02 2:2 rodando...")
app.run_polling()
