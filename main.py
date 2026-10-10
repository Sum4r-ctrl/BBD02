import ccxt, asyncio, time, numpy as np, os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINGX_API_KEY = os.getenv("BINGX_API_KEY")
BINGX_SECRET = os.getenv("BINGX_SECRET")

bingx = ccxt.bingx({
    'apiKey': BINGX_API_KEY,
    'secret': BINGX_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

banca = 3.5 # COMEÇA COM 3.5
rodando = False

def criterio_forte(qtd=1):
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
                candidatos.append((simbolo, score))
            except:
                continue
        candidatos.sort(key=lambda x: x[1], reverse=True)
        if qtd == 1:
            return [candidatos[0][0]] if candidatos else ["PEPE/USDT"]
        else:
            if len(candidatos) >= 2: return [candidatos[0][0], candidatos[1][0]]
            elif len(candidatos) == 1: return [candidatos[0][0], "PEPE/USDT"]
            else: return ["PEPE/USDT", "WIF/USDT"]
    except:
        return ["PEPE/USDT"] if qtd==1 else ["PEPE/USDT", "WIF/USDT"]

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global rodando, banca
    rodando = True
    modo = "1 TOKEN" if banca < 4 else "2:2"
    await update.message.reply_text(f"🚀 BOT BBD02 LIGADO\nBanca: ${banca} Modo: {modo}\nFiltro firme ON")

    while rodando:
        try:
            qtd_moedas = 1 if banca < 4 else 2
            moedas = criterio_forte(qtd_moedas)
            banca_par = banca / qtd_moedas

            compras = []
            for moeda in moedas:
                p = bingx.fetch_ticker(moeda)['last']
                qtd = banca_par / p
                bingx.create_market_buy_order(moeda, qtd)
                compras.append((moeda, p, qtd))
                await update.message.reply_text(f"📥 COMPREI {moeda} ${banca_par:.2f}")
                await asyncio.sleep(1)

            # Monitorar vendas
            vendas_pendentes = {m[0]: (m[1], m[2]) for m in compras}
            lucros = {}

            while rodando and vendas_pendentes:
                for moeda in list(vendas_pendentes.keys()):
                    try:
                        entrada, qtd = vendas_pendentes[moeda]
                        atual = bingx.fetch_ticker(moeda)['last']
                        pnl = (atual - entrada) / entrada
                        limite = 0.12 if qtd_moedas==1 else 0.12
                        if pnl >= 0.25 or pnl <= -0.12:
                            bingx.create_market_sell_order(moeda, qtd)
                            lucros[moeda] = banca_par * pnl
                            del vendas_pendentes[moeda]
                            await update.message.reply_text(f"{'✅' if pnl>0 else '🛑'} {moeda} {pnl*100:.1f}%")
                    except:
                        continue
                await asyncio.sleep(5)

            banca += sum(lucros.values())
            proximo_modo = "1 TOKEN" if banca < 4 else "2:2"
            await update.message.reply_text(f"🔄 Ciclo fechado. Banca: ${banca:.2f}\nPróximo modo: {proximo_modo}\nBuscando...")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Erro: {e} - reiniciando...")
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
        await update.message.reply_text("Use: /banca 3.5")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("iniciar", iniciar))
app.add_handler(CommandHandler("parar", parar))
app.add_handler(CommandHandler("banca", set_banca))
print(f"Bot BBD02 {banca}$ pronto...")
app.run_polling()
