#!/usr/bin/env python3

-- coding: utf-8 --

── 0) Monkey-patch APScheduler timezone issue ──

import apscheduler.util import pytz

def _safe_astimezone(timezone): if timezone is None: return pytz.UTC if hasattr(timezone, "utcoffset"): return timezone name = timezone if isinstance(timezone, str) else getattr(timezone, "zone", None) if name: try: return pytz.timezone(name) except: pass return pytz.UTC

apscheduler.util.astimezone = _safe_astimezone

── Imports estándar ──

import logging from datetime import datetime from telegram import Update, ReplyKeyboardMarkup from telegram.ext import ( Application, CommandHandler, MessageHandler, filters, ContextTypes, ) from config_manager import load_config, save_config, load_mensajes, save_mensajes

── Logging ──

logging.basicConfig( format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO ) logger = logging.getLogger(name)

── Teclados ──

MAIN_KB = ReplyKeyboardMarkup([ ["🔗 Vincular Canal", "📂 Destinos"], ["✏️ Editar Mensaje", "🗑️ Eliminar Mensaje"], ["🔁 Cambiar Intervalo", "🌐 Cambiar Zona"], ["📄 Estado del Bot"] ], resize_keyboard=True)

BACK_KB = ReplyKeyboardMarkup([["🔙 Volver"]], resize_keyboard=True)

class TelegramForwarderBot: def init(self, token): self.config = load_config() self.mensajes = load_mensajes() self.token = token

def _is_admin(self, uid):
    return uid == self.config.get("admin_id")

async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not self._is_admin(uid):
        return await update.message.reply_text(
            "❌ *Acceso denegado.*",
            parse_mode="Markdown",
            reply_markup=MAIN_KB
        )
    await self._show_main_menu(update)

async def _show_main_menu(self, update: Update):
    text = (
        "🚀 *Menú Principal*\n\n"
        f"📺 Origen: `{self.config.get('origen_chat_id','No asignado')}`\n"
        f"👥 Destinos: {len(self.config.get('destinos',[]))}\n"
        f"📁 Listas: {len(self.config.get('listas_destinos',{}))}\n"
        f"📨 Mensajes: {len(self.mensajes)}\n"
        f"⏱️ Intervalo: {self.config.get('intervalo_segundos',60)}s\n"
        f"🌐 Zona: `{self.config.get('timezone','UTC')}`\n\n"
        "Selecciona una opción:"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KB, parse_mode="Markdown")

async def message_handler(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not self._is_admin(uid):
        return

    text = update.message.text.strip() if update.message.text else ""
    waiting = ctx.user_data.get("waiting_for")

    # ── 1) Vincular Canal ──
    if text == "🔗 Vincular Canal":
        await update.message.reply_text(
            "📤 *Reenvía un mensaje* desde tu canal de origen.",
            parse_mode="Markdown", reply_markup=BACK_KB
        )
        ctx.user_data["waiting_for"] = "channel_forward"
        return

    if waiting == "channel_forward":
        fchat = getattr(update.message, 'forward_from_chat', None)
        if fchat:
            cid = fchat.id
            self.config["origen_chat_id"] = str(cid)
            save_config(self.config)
            await update.message.reply_text(
                f"✅ Canal vinculado: `{cid}`",
                parse_mode="Markdown", reply_markup=MAIN_KB
            )
            ctx.user_data.pop("waiting_for")
            return

    # ── 2) Gestión de Destinos ──
    if text == "📂 Destinos":
        kb = ReplyKeyboardMarkup([
            ["➕ Agregar Destino","🗑️ Eliminar Destino"],
            ["📁 Crear Lista","📂 Gestionar Listas"],
            ["🔙 Volver"]
        ], resize_keyboard=True)
        await update.message.reply_text("📂 *Gestión de Destinos*", parse_mode="Markdown", reply_markup=kb)
        ctx.user_data["waiting_for"] = "destinos_menu"
        return

    if waiting == "destinos_menu":
        # Agregar Destino
        if text == "➕ Agregar Destino":
            await update.message.reply_text("📝 Envía ID del destino:", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "add_destino"
            return
        # Eliminar Destino
        if text == "🗑️ Eliminar Destino":
            ds = self.config.get("destinos", [])
            if not ds:
                await update.message.reply_text("⚠️ No hay destinos.", reply_markup=MAIN_KB)
            else:
                lines = "\n".join(f"{i+1}. {d}" for i,d in enumerate(ds))
                await update.message.reply_text(
                    f"🗑️ Selecciona número:\n{lines}", parse_mode="Markdown", reply_markup=BACK_KB
                )
                ctx.user_data["waiting_for"] = "del_destino"
            return
        # Crear Lista
        if text == "📁 Crear Lista":
            await update.message.reply_text("📌 Nombre de la nueva lista:", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "new_list_name"
            return
        # Gestionar Listas
        if text == "📂 Gestionar Listas":
            lists = self.config.get("listas_destinos", {})
            if not lists:
                await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KB)
            else:
                menu = [[n] for n in lists.keys()]+[["🔙 Volver"]]
                await update.message.reply_text(
                    "📂 *Listas Disponibles:*", parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
                )
                ctx.user_data["waiting_for"] = "manage_lists"
            return
        # Volver
        if text == "🔙 Volver":
            await self._show_main_menu(update)
            ctx.user_data.pop("waiting_for")
            return

    if waiting == "add_destino":
        d = text
        lst = self.config.setdefault("destinos", [])
        if d not in lst:
            lst.append(d)
            save_config(self.config)
            await update.message.reply_text(f"✅ Destino `{d}` agregado.", parse_mode="Markdown", reply_markup=MAIN_KB)
        else:
            await update.message.reply_text("⚠️ Ya existe.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return

    if waiting == "del_destino":
        try:
            idx = int(text)-1
            d = self.config["destinos"].pop(idx)
            save_config(self.config)
            await update.message.reply_text(f"✅ Destino `{d}` eliminado.", reply_markup=MAIN_KB)
        except:
            await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return

    if waiting == "new_list_name":
        ctx.user_data["new_list_name"] = text
        await update.message.reply_text("📋 Ahora envía los IDs (coma o línea):", reply_markup=BACK_KB)
        ctx.user_data["waiting_for"] = "new_list_ids"
        return
    if waiting == "new_list_ids":
        name = ctx.user_data.pop("new_list_name")
        ids = [x.strip() for x in text.replace("\n",",").split(",") if x.strip()]
        self.config.setdefault("listas_destinos", {})[name] = ids
        save_config(self.config)
        await update.message.reply_text(f"✅ Lista `{name}` creada con {len(ids)} destinos.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return

    if waiting == "manage_lists":
        if text == "🔙 Volver":
            await self._show_main_menu(update)
            ctx.user_data.pop("waiting_for")
            return
        name = text
        if name in self.config.get("listas_destinos", {}):
            kb = ReplyKeyboardMarkup([
                ["📋 Ver","❌ Eliminar"],["🔙 Volver"]
            ], resize_keyboard=True)
            await update.message.reply_text(f"📂 *{name}* ({len(self.config['listas_destinos'][name])})", parse_mode="Markdown", reply_markup=kb)
            ctx.user_data["waiting_for"] = f"list_{name}"
        return

    if waiting and waiting.startswith("list_"):
        name = waiting.split("_",1)[1]
        if text == "📋 Ver":
            ids = self.config["listas_destinos"].get(name, [])
            await update.message.reply_text("\n".join(ids) or "Ninguno", reply_markup=MAIN_KB)
        elif text == "❌ Eliminar":
            self.config["listas_destinos"].pop(name, None)
            save_config(self.config)
            await update.message.reply_text(f"❌ Lista `{name}` eliminada.", reply_markup=MAIN_KB)
        else:
            await self._show_main_menu(update)
        ctx.user_data.pop("waiting_for")
        return

    # ── 3) Captura de mensaje reenviado ──
    fchat2 = getattr(update.message, 'forward_from_chat', None)
    if fchat2 and str(fchat2.id) == str(self.config.get("origen_chat_id")):
        mid = getattr(update.message, 'forward_from_message_id', None)
        nuevo = {
            "from_chat_id": fchat2.id,
            "message_id": mid,
            "intervalo_segundos": self.config.get("intervalo_segundos",60),
            "dest_all": True,
            "dest_list": None,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.mensajes.append(nuevo)
        save_mensajes(self.mensajes)
        kb = ReplyKeyboardMarkup([
            ["👥 A Todos","📋 Lista"],["✅ Guardar","❌ Cancelar"],
            ["🏁 Finalizar"],["🔙 Volver"]
        ], resize_keyboard=True)
        await update.message.reply_text(
            f"🔥 *Nuevo Mensaje Detectado!*\nID: `{mid}`\nIntervalo: `{nuevo['intervalo_segundos']}s`\nElige destino:",
            parse_mode="Markdown", reply_markup=kb
        )
        ctx.user_data["waiting_for"] = f"msg_cfg_{len(self.mensajes)-1}"
        return

    # ── 4) Configuración puntual de mensaje reenviado ──
    if waiting and waiting.startswith("msg_cfg_"):
        idx = int(waiting.split("_")[-1])
        m = self.mensajes[idx]
        if text == "👥 A Todos":
            m["dest_all"], m["dest_list"] = True, None
            save_mensajes(self.mensajes)
            await update.message.reply_text("✅ Enviar a todos.", reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "📋 Lista":
            lists = self.config.get("listas_destinos",{})
            if not lists:
                await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KB)
                ctx.user_data.pop("waiting_for")
            else:
                kb = ReplyKeyboardMarkup([[n] for n in lists]+[["🔙 Volver"]], resize_keyboard=True)
                await update.message.reply_text("📋 Elige lista:", reply_markup=kb)
                ctx.user_data["waiting_for"] = f"msg_list_{idx}"
        elif waiting.startswith("msg_list_"):
            if text == "🔙 Volver":
                await self._show_main_menu(update)
            else:
                m["dest_all"], m["dest_list"] = False, text
                save_mensajes(self.mensajes)
                await update.message.reply_text(f"✅ Lista `{text}` seleccionada.", reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "✅ Guardar":
            await update.message.reply_text("✅ Mensaje guardado.", reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "❌ Cancelar":
            self.mensajes.pop(idx)
            save_mensajes(self.mensajes)
            await update.message.reply_text("❌ Mensaje descartado.", reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        elif text == "🏁 Finalizar":
            if not hasattr(ctx.application, "forwarder_job"):
                interval = self.config.get("intervalo_segundos",60)
                ctx.application.forwarder_job = ctx.job_queue.run_repeating(
                    self._reenviar_mensajes, interval=interval, first=interval
                )
            await update.message.reply_text("🏁 ¡Reenvío iniciado!", reply_markup=MAIN_KB)
            ctx.user_data.pop("waiting_for")
        return

    # ── 5) Editar Mensaje ──
    if text == "✏️ Editar Mensaje":
        if not self.mensajes:
            await update.message.reply_text("⚠️ No hay mensajes.", reply_markup=MAIN_KB)
            return
        lines = [f"{i+1}. {m['message_id']} ({m['intervalo_segundos']}s)" for i,m in enumerate(self.mensajes)]
        await update.message.reply_text(
            "✏️ Selecciona número para cambiar intervalo:\n"+"\n".join(lines),
            parse_mode="Markdown", reply_markup=BACK_KB
        )
        ctx.user_data["waiting_for"] = "edit_msg_select"
        return
    if waiting == "edit_msg_select":
        try:
            idx = int(text)-1
            ctx.user_data["edit_idx"] = idx
            await update.message.reply_text("🕒 Nuevo intervalo (s):", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "edit_msg_value"
        except:
            await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KB)
        return
    if waiting == "edit_msg_value":
        try:
            v = int(text); idx = ctx.user_data.pop("edit_idx")
            self.mensajes[idx]["intervalo_segundos"] = v
            save_mensajes(self.mensajes)
            await update.message.reply_text(f"✅ Intervalo actualizado a {v}s", reply_markup=MAIN_KB)
        except:
            await update.message.reply_text("❌ Valor inválido.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return

    # ── 6) Eliminar Mensaje ──
    if text == "🗑️ Eliminar Mensaje":
        if not self.mensajes:
            await update.message.reply_text("⚠️ No hay mensajes.", reply_markup=MAIN_KB)
            return
        lines = [f"{i+1}. {m['message_id']}" for i,m in enumerate(self.mensajes)]
        await update.message.reply_text(
            "🗑️ Selecciona número para eliminar:\n"+"\n".join(lines),
            parse_mode="Markdown", reply_markup=BACK_KB
        )
        ctx.user_data["waiting_for"] = "del_msg_select"
        return
    if waiting == "del_msg_select":
        try:
            idx = int(text)-1; m = self.mensajes.pop(idx)
            save_mensajes(self.mensajes)
            await update.message.reply_text(f"✅ Mensaje `{m['message_id']}` eliminado.", reply_markup=MAIN_KB)
        except:
            await update.message.reply_text("❌ Selección inválida.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return

    # ── 7) Cambiar Intervalo ──
    if text == "🔁 Cambiar Intervalo":
        kb = ReplyKeyboardMarkup([
            ["🔁 Global","✏️ Por Mensaje"],["📋 Por Lista","🔙 Volver"]
        ], resize_keyboard=True)
        await update.message.reply_text("🕒 *Modo Intervalo:*", parse_mode="Markdown", reply_markup=kb)
        ctx.user_data["waiting_for"] = "interval_menu"
        return
    if waiting == "interval_menu":
        if text == "🔁 Global":
            await update.message.reply_text("🕒 Nuevo global (s):", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "int_global"
        elif text == "✏️ Por Mensaje":
            await update.message.reply_text("✏️ ID de mensaje:", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "int_msg_id"
        elif text == "📋 Por Lista":
            lists = self.config.get("listas_destinos",{})
            if not lists:
                await update.message.reply_text("⚠️ No hay listas.", reply_markup=MAIN_KB)
                ctx.user_data.pop("waiting_for")
            else:
                kb2 = ReplyKeyboardMarkup([[n] for n in lists]+[["🔙 Volver"]], resize_keyboard=True)
                await update.message_reply_text("📋 Elige lista:", reply_markup=kb2)
                ctx.user_data["waiting_for"] = "int_list_sel"
        else:
            await self._show_main_menu(update)
            ctx.user_data.pop("waiting_for")
        return
    if waiting == "int_global":
        try:
            v = int(text); self.config["intervalo_segundos"] = v; save_config(self.config)
            await update.message.reply_text(f"✅ Intervalo global: {v}s", reply_markup=MAIN_KB)
        except:
            await update.message.reply_text("❌ Número inválido.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return
    if waiting == "int_msg_id":
        try:
            idx = int(text)-1; ctx.user_data["int_msg_idx"] = idx
            await update.message.reply_text("🕒 Nuevo (s):", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "int_msg_val"
        except:
            await update.message_reply_text("❌ Selección inválida.", reply_markup=MAIN_KB)
        return
    if waiting == "int_msg_val":
        try:
            v = int(text); idx = ctx.user_data.pop("int_msg_idx")
            self.mensajes[idx]["intervalo_segundos"] = v; save_mensajes(self.mensajes)
            await update.message_reply_text(f"✅ Mensaje {idx+1}: {v}s", reply_markup=MAIN_KB)
        except:
            await update.message_reply_text("❌ Error.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return
    if waiting == "int_list_sel":
        if text == "🔙 Volver":
            await self._show_main_menu(update); ctx.user_data.pop("waiting_for")
        else:
            ctx.user_data["int_list_name"] = text
            await update.message.reply_text("🕒 Nuevo (s):", reply_markup=BACK_KB)
            ctx.user_data["waiting_for"] = "int_list_val"
        return
    if waiting == "int_list_val":
        try:
            v = int(text); name = ctx.user_data.pop("int_list_name")
            for m in self.mensajes:
                if m.get("dest_list")==name:
                    m["intervalo_segundos"] = v
            save_mensajes(self.mensajes)
            await update.message.reply_text(f"✅ Lista `{name}`: {v}s", reply_markup=MAIN_KB)
        except:
            await update.message.reply_text("❌ Error.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return

    # ── 8) Cambiar Zona Horaria ──
    if text == "🌐 Cambiar Zona":
        await update.message.reply_text("🌐 Nueva zona (p.ej. Europe/Madrid):", reply_markup=BACK_KB)
        ctx.user_data["waiting_for"] = "timezone"
        return
    if waiting == "timezone":
        try:
            pytz.timezone(text); self.config["timezone"] = text; save_config(self.config)
            await update.message.reply_text(f"✅ Zona: `{text}`", parse_mode="Markdown", reply_markup=MAIN_KB)
        except:
            await update.message.reply_text("❌ Zona inválida.", reply_markup=MAIN_KB)
        ctx.user_data.pop("waiting_for")
        return

    # ── 9) Estado del Bot ──
    if text == "📄 Estado del Bot":
        await self._show_main_menu(update)
        return

async def _reenviar_mensajes(self, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🔄 Ciclo de reenvío...")
    for m in self.mensajes:
        dests = self.config["destinos"] if m.get("dest_all", True) else self.config["listas_destinos"].get(m.get("dest_list"), [])
        for d in dests:
            try:
                await context.bot.forward_message(chat_id=d, from_chat_id=m["from_chat_id"], message_id=m["message_id"])
                logger.info(f"✔️ {m['message_id']} → {d}")
            except Exception as e:
                logger.error(f"❌ {m['message_id']} → {d}: {e}")

def run(self):
    app = Application.builder().token(self.token).build()
    app.add_handler(CommandHandler("start", self.start))
    app.add_handler(MessageHandler(filters.ALL, self.message_handler))
    logger.info("🚀 Bot iniciado")
    app.run_polling()

if name == "main": conf = load_config() token = conf.get("bot_token") if not token: logger.error("❌ Debes definir bot_token en config.json") exit(1) TelegramForwarderBot(token).run()

