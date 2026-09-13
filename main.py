import os
import sqlite3
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------
# FLASK SERVER (24/7 EN RENDER)
# ---------------------------------------------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot en linea"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ---------------------------------------------------------
# BASE DE DATOS (SQLITE)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS welcome_config (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            message TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS help_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            label TEXT,
            response_text TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS help_panel_config (
            guild_id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# BOT DISCORD SETUP
# ---------------------------------------------------------
MY_USER_ID = 1491476806203740373

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="-", intents=intents)

def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == MY_USER_ID

# ---------------------------------------------------------
# COMPONENTES Y VIEWS (BOTONES / SELECTS)
# ---------------------------------------------------------
class DynamicHelpView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        conn = sqlite3.connect("bot_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, label, response_text FROM help_buttons WHERE guild_id = ?", (guild_id,))
        rows = cursor.fetchall()
        conn.close()

        for btn_id, label, response_text in rows:
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary,
                custom_id=f"help_btn_{btn_id}"
            )
            
            async def btn_callback(interaction: discord.Interaction, resp=response_text):
                embed = discord.Embed(
                    description=resp,
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            button.callback = btn_callback
            self.add_item(button)

class RoleSelect(discord.ui.Select):
    def __init__(self, message_id: int, roles: list[discord.Role]):
        self.target_message_id = message_id
        options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in roles[:25]]
        super().__init__(
            placeholder="Selecciona los roles para la reaccion",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_roles = [interaction.guild.get_role(int(v)) for v in self.values]
        role_names = "\n".join([f"• {r.name}" for r in selected_roles if r])
        
        embed = discord.Embed(
            title="Roles Listos",
            description=f"Agregados al sistema de reaccion:\n\n{role_names}\n\nReacciona al mensaje `{self.target_message_id}` con tu emoji.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self, message_id: int, roles: list[discord.Role]):
        super().__init__(timeout=120)
        self.add_item(RoleSelect(message_id, roles))

# ---------------------------------------------------------
# EVENTOS
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, message FROM welcome_config WHERE guild_id = ?", (member.guild.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        channel_id, raw_msg = row
        channel = member.guild.get_channel(channel_id)
        if channel:
            msg = raw_msg.replace("{user}", member.mention).replace("{server}", member.guild.name)
            embed = discord.Embed(
                title="Bienvenido",
                description=msg,
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)

# ---------------------------------------------------------
# COMANDOS PREFIX (REGLA DE ORO: ID TUTUSITO_0213)
# ---------------------------------------------------------
@bot.command(name="setupcanales")
async def setupcanales(ctx):
    if ctx.author.id != MY_USER_ID:
        return

    guild = ctx.guild

    # Borrar todos los canales y categorías existentes
    for channel in list(guild.channels):
        try:
            await channel.delete()
        except Exception:
            pass

    # Categoría 1
    cat1 = await guild.create_category("☢️ Chernoblix (Info)")
    await guild.create_text_channel("⚠️-anuncios", category=cat1)
    await guild.create_text_channel("👮🏻-normas", category=cat1)
    await guild.create_text_channel("🤔-ayuda", category=cat1)

    # Categoría 2
    cat2 = await guild.create_category("☢️ Prison Life 👮🏻")
    await guild.create_text_channel("👮🏻-anuncios-pl", category=cat2)
    await guild.create_text_channel("🎦-clips", category=cat2)
    await guild.create_text_channel("🪪-roles", category=cat2)

    # Categoría 3
    cat3 = await guild.create_category("☢️ Social Chernoblix")
    chat_principal = await guild.create_text_channel("💬-chat", category=cat3)
    await guild.create_text_channel("🧌-memes", category=cat3)
    await guild.create_text_channel("🎮-reunión-partidas", category=cat3)
    await guild.create_voice_channel("🎮 | Reunión VC", category=cat3)

    await chat_principal.send("Estructura de canales creada correctamente.")

@bot.command(name="purge")
async def purge(ctx, cantidad: int = 10):
    if ctx.author.id != MY_USER_ID:
        return
    
    await ctx.channel.purge(limit=cantidad + 1)

@bot.command(name="rc")
async def rc(ctx):
    if ctx.author.id != MY_USER_ID:
        return

    channel = ctx.channel
    pos = channel.position
    
    # Clonar el canal preservando categoría, nombre y permisos
    new_channel = await channel.clone()
    await channel.delete()
    await new_channel.edit(position=pos)
    await new_channel.send("Canal reestablecido.")

@bot.command(name="panelayuda")
async def panelayuda(ctx):
    # Este comando lo pueden invocar todos, pero interactúan mediante los botones
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, description FROM help_panel_config WHERE guild_id = ?", (ctx.guild.id,))
    row = cursor.fetchone()
    conn.close()

    title = row[0] if row else "Panel de Ayuda"
    desc = row[1] if row else "Presiona los botones de abajo para ver la información."

    embed = discord.Embed(
        title=title,
        description=desc,
        color=discord.Color.dark_grey()
    )
    view = DynamicHelpView(ctx.guild.id)
    await ctx.send(embed=embed, view=view)

# ---------------------------------------------------------
# COMANDOS DASH / SLASH (REGLA DE ORO: ID TUTUSITO_0213)
# ---------------------------------------------------------
@bot.tree.command(name="embed", description="Crea un mensaje embed")
@app_commands.describe(titulo="Titulo del embed", descripcion="Texto del embed")
async def embed_cmd(interaction: discord.Interaction, titulo: str, descripcion: str):
    if not is_owner(interaction):
        await interaction.response.send_message("Sin permiso.", ephemeral=True)
        return

    embed = discord.Embed(
        title=titulo,
        description=descripcion,
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("Enviado.", ephemeral=True)

@bot.tree.command(name="configpanel", description="Configura elementos del panel de ayuda")
@app_commands.describe(
    titulo="Titulo principal del panel",
    descripcion="Texto principal del panel",
    nuevo_boton_texto="Nombre del nuevo boton",
    nuevo_boton_respuesta="Respuesta del nuevo boton"
)
async def configpanel(
    interaction: discord.Interaction,
    titulo: str = None,
    descripcion: str = None,
    nuevo_boton_texto: str = None,
    nuevo_boton_respuesta: str = None
):
    if not is_owner(interaction):
        await interaction.response.send_message("Sin permiso.", ephemeral=True)
        return

    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()

    if titulo or descripcion:
        cursor.execute("""
            INSERT INTO help_panel_config (guild_id, title, description)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
            title = COALESCE(excluded.title, title),
            description = COALESCE(excluded.description, description)
        """, (interaction.guild.id, titulo, descripcion))

    if nuevo_boton_texto and nuevo_boton_respuesta:
        cursor.execute("""
            INSERT INTO help_buttons (guild_id, label, response_text)
            VALUES (?, ?, ?)
        """, (interaction.guild.id, nuevo_boton_texto, nuevo_boton_respuesta))

    conn.commit()
    conn.close()

    await interaction.response.send_message("Configuracion del panel actualizada.", ephemeral=True)

@bot.tree.command(name="reactionroles", description="Configura roles por reaccion")
@app_commands.describe(message_id="ID del mensaje destino")
async def reactionroles(interaction: discord.Interaction, message_id: str):
    if not is_owner(interaction):
        await interaction.response.send_message("Sin permiso.", ephemeral=True)
        return

    try:
        msg_id = int(message_id)
    except ValueError:
        await interaction.response.send_message("ID invalido.", ephemeral=True)
        return

    roles = [r for r in interaction.guild.roles if r != interaction.guild.default_role]
    if not roles:
        await interaction.response.send_message("No hay roles disponibles.", ephemeral=True)
        return

    view = RoleSelectView(msg_id, roles)
    await interaction.response.send_message("Selecciona los roles:", view=view, ephemeral=True)

@bot.tree.command(name="bienvenida", description="Configura mensajes de bienvenida")
@app_commands.describe(
    canal="Canal para el mensaje",
    mensaje="Usa {user} para mención y {server} para el servidor"
)
async def bienvenida(interaction: discord.Interaction, canal: discord.TextChannel, mensaje: str):
    if not is_owner(interaction):
        await interaction.response.send_message("Sin permiso.", ephemeral=True)
        return

    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO welcome_config (guild_id, channel_id, message)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
        channel_id = excluded.channel_id,
        message = excluded.message
    """, (interaction.guild.id, canal.id, mensaje))
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"Bienvenida establecida en {canal.mention}", ephemeral=True)

@bot.tree.command(
    name="msj",
    description="Envía un mensaje, archivo, respuesta o reacción de forma anónima.",
)
@app_commands.describe(
    canal="Canal donde se enviará el mensaje (opcional, por defecto el actual)",
    texto="Texto o mensaje a enviar",
    archivo="Imagen, video o archivo adjunto",
    reply_to="ID del mensaje al que quieres responder",
    reaccionar_to="ID del mensaje al que quieres reaccionar",
    emoji="Emoji para reaccionar (requiere reaccionar_to)",
)
async def msj(
    interaction: discord.Interaction,
    canal: discord.TextChannel = None,
    texto: str = None,
    archivo: discord.Attachment = None,
    reply_to: str = None,
    reaccionar_to: str = None,
    emoji: str = None,
):
    # REGLA DE ORO: Verificación estricta de ID
    if interaction.user.id != 1491476806203740373:
        await interaction.response.send_message("Sin permiso.", ephemeral=True)
        return

    target_channel = canal or interaction.channel
    file_to_send = await archivo.to_file() if archivo else None

    # Manejar reacción
    if reaccionar_to and emoji:
        try:
            msg_id = int(reaccionar_to)
            target_msg = await target_channel.fetch_message(msg_id)
            await target_msg.add_reaction(emoji)
        except Exception as e:
            await interaction.response.send_message(
                f"Error al reaccionar: {e}", ephemeral=True
            )
            return

    # Manejar envío de mensaje o respuesta
    if texto or file_to_send:
        try:
            if reply_to:
                msg_id = int(reply_to)
                target_msg = await target_channel.fetch_message(msg_id)
                await target_msg.reply(content=texto, file=file_to_send)
            else:
                await target_channel.send(content=texto, file=file_to_send)
        except Exception as e:
            await interaction.response.send_message(
                f"Error al enviar mensaje: {e}", ephemeral=True
            )
            return

    await interaction.response.send_message(
        "Acción ejecutada correctamente.", ephemeral=True
    )
    

@bot.command(name="ayuda")
async def ayuda(ctx):
    # REGLA DE ORO: Verificación estricta de ID
    if ctx.author.id != 1491476806203740373:
        return

    embed = discord.Embed(
        title="Panel de Control del Bot",
        description="Lista de comandos del servidor:",
        color=discord.Color.dark_red()
    )

    embed.add_field(
        name="Comandos de Prefijo (-)",
        value=(
            "• `-setupcanales`: Borra todos los canales existentes y crea la estructura oficial.\n"
            "• `-purge [cantidad]`: Elimina el número de mensajes especificado en el canal.\n"
            "• `-rc`: Reestablece/clona el canal actual manteniendo su posición y configuración.\n"
            "• `-panelayuda`: Muestra el panel interactivo público con botones.\n"
            "• `-ayuda`: Muestra esta lista de comandos."
        ),
        inline=False
    )

    embed.add_field(
        name="Comandos de Barra (/)",
        value=(
            "• `/embed [titulo] [descripcion]`: Envía un mensaje embed sin mostrar quién lo creó.\n"
            "• `/configpanel [titulo] [descripcion] [nuevo_boton_texto] [nuevo_boton_respuesta]`: Configura las respuestas y botones del panel de ayuda.\n"
            "• `/reactionroles [message_id]`: Configura un panel para asignar roles mediante reacciones.\n"
            "• `/bienvenida [canal] [mensaje]`: Configura el canal y texto de bienvenida automática.\n"
            "• `/msj [canal] [texto] [archivo] [reply_to] [reaccionar_to] [emoji]`: Envía mensajes, imágenes, videos, responde o reacciona de forma anónima."
        ),
        inline=False
    )

    embed.set_footer(text="Acceso exclusivo asignado.")
    await ctx.send(embed=embed)
    
# ---------------------------------------------------------
# INICIO
# ---------------------------------------------------------
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Falta la variable de entorno DISCORD_TOKEN.")

