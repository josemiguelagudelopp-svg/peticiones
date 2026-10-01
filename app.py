import os
import time
import requests
import customtkinter as ctk
from supabase import create_client, Client
import threading
import whisper
import qrcode
from PIL import Image, ImageTk
from datetime import datetime

# CONFIGURACIÓN DE SUPABASE
SUPABASE_URL = "https://rogfrmfhvanrbrhjeyzt.supabase.co"
SUPABASE_KEY = "sb_publishable_ARmpZsdwoh_WOty-qnmOsg_abb3QoVL"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

print("Cargando modelo Whisper (esto puede tardar unos segundos la primera vez)...")
model = whisper.load_model("base")
print("¡Modelo Whisper listo!")

class AppEscritorio(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Receptor de Peticiones Web - Panel Profesional")
        self.geometry("550, 750")

        self.ids_vistos = set()

        # Título principal
        self.label_titulo = ctk.CTkLabel(self, text="Panel de Peticiones en Tiempo Real", font=ctk.CTkFont(size=18, weight="bold"))
        self.label_titulo.pack(pady=15)

        # Contenedor con scroll para las tarjetas
        self.scroll_frame = ctk.CTkScrollableFrame(self, width=500, height=620)
        self.scroll_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Cargar registros iniciales e iniciar sondeo cada 3 segundos
        self.verificar_nuevas_peticiones()
        self.iniciar_polling()

    def verificar_nuevas_peticiones(self):
        try:
            response = supabase.table("peticiones").select("*").execute()
            registros = response.data
            
            if registros:
                registros_ordenados = sorted(registros, key=lambda x: x.get("id", 0), reverse=True)
                
                for reg in registros_ordenados:
                    reg_id = reg.get("id")
                    if reg_id not in self.ids_vistos:
                        self.ids_vistos.add(reg_id)
                        self.after(0, lambda r=reg: self.agregar_peticion_ui(
                            r.get("id"), 
                            r.get("texto1"),  # Profesor
                            r.get("texto2"),  # Materia
                            r.get("audio_url"), 
                            r.get("transcripcion", "Pendiente..."),
                            r.get("created_at")
                        ))
        except Exception as e:
            print("Error detallado al verificar peticiones:", e)

    def iniciar_polling(self):
        def loop_polling():
            while True:
                time.sleep(3)
                self.verificar_nuevas_peticiones()

        hilo = threading.Thread(target=loop_polling, daemon=True)
        hilo.start()

    def agregar_peticion_ui(self, record_id, profesor, materia, audio_url, transcripcion_inicial, created_at):
        fecha_formateada = "Reciente"
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                fecha_formateada = dt.strftime("%d/%m/%Y %I:%M %p")
            except:
                pass

        # Tarjeta contenedora
        card = ctk.CTkFrame(self.scroll_frame, fg_color=("#f0f0f0", "#242424"), corner_radius=8, border_width=1, border_color=("#d0d0d0", "#383838"))
        card.pack(fill="x", padx=5, pady=10, ipadx=10, ipady=10)

        # Cabecera de la tarjeta: ID y Fecha
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=2)

        lbl_id = ctk.CTkLabel(header_frame, text=f"📌 Petición #{record_id}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#3498db")
        lbl_id.pack(side="left")

        lbl_fecha = ctk.CTkLabel(header_frame, text=f"🕒 {fecha_formateada}", font=ctk.CTkFont(size=11), text_color="gray")
        lbl_fecha.pack(side="right")

        # Textos actualizados: Profesor y Materia
        lbl_profesor = ctk.CTkLabel(card, text=f"👨‍🏫 Profesor: {profesor}", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_profesor.pack(anchor="w", padx=5, pady=2)

        lbl_materia = ctk.CTkLabel(card, text=f"📖 Materia: {materia}", font=ctk.CTkFont(size=13))
        lbl_materia.pack(anchor="w", padx=5, pady=2)

        # Transcripción
        lbl_transcripcion = ctk.CTkLabel(card, text=f"Transcripción: {transcripcion_inicial}", text_color="#2ecc71", font=ctk.CTkFont(size=13, weight="bold"), wraplength=460, justify="left")
        lbl_transcripcion.pack(anchor="w", padx=5, pady=5)

        # --- FILA DE ACCIONES Y BOTONES ---
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.pack(fill="x", padx=5, pady=5)

        # Botón transcribir y oír
        btn_procesar = ctk.CTkButton(
            actions_frame, 
            text="🎙️ Transcribir", 
            width=110, 
            fg_color="#2980b9", 
            hover_color="#2471a3", 
            command=lambda: threading.Thread(target=self.descargar_y_transcribir, args=(audio_url, record_id, lbl_transcripcion, btn_qr, profesor, materia, fecha_formateada)).start()
        )
        btn_procesar.pack(side="left", padx=2)

        # Botón QR para escanear con el celular (pasando todos los datos estructurados)
        btn_qr = ctk.CTkButton(
            actions_frame, 
            text="📱 Ver QR", 
            width=85, 
            fg_color="#8e44ad", 
            hover_color="#732d91", 
            command=lambda: self.mostrar_qr(record_id, profesor, materia, lbl_transcripcion.cget("text").replace("Transcripción: ", ""), fecha_formateada)
        )
        btn_qr.pack(side="left", padx=2)

        # Casilla de verificación
        chk_hecho = ctk.CTkCheckBox(actions_frame, text="Hecho", font=ctk.CTkFont(size=12))
        chk_hecho.pack(side="left", padx=10)

        # Botón Eliminar elemento
        btn_eliminar = ctk.CTkButton(
            actions_frame, 
            text="🗑️ Borrar", 
            width=75, 
            fg_color="#c0392b", 
            hover_color="#962d22", 
            command=lambda: self.eliminar_peticion(record_id, card)
        )
        btn_eliminar.pack(side="right", padx=2)

    def descargar_y_transcribir(self, url, record_id, lbl_transcripcion, btn_qr, profesor, materia, fecha):
        try:
            lbl_transcripcion.configure(text="Transcripción: Descargando audio...")
            response = requests.get(url)
            local_path = f"audio_{record_id}.webm"
            with open(local_path, "wb") as f:
                f.write(response.content)
            
            lbl_transcripcion.configure(text="Transcripción: Transcribiendo con Whisper...")
            
            result = model.transcribe(local_path, language="es")
            texto_transcrito = result["text"].strip()
            
            self.after(0, lambda: lbl_transcripcion.configure(text=f"Transcripción: {texto_transcrito}"))
            
            # Actualizar el comando del botón QR dinámicamente con la nueva transcripción lista
            btn_qr.configure(command=lambda: self.mostrar_qr(record_id, profesor, materia, texto_transcrito, fecha))
            
            supabase.table("peticiones").update({"transcripcion": texto_transcrito}).eq("id", record_id).execute()

            os.system(f"start {local_path}" if os.name == "nt" else f"open {local_path}")
            
        except Exception as e:
            print("Error en la transcripción:", e)
            self.after(0, lambda: lbl_transcripcion.configure(text="Transcripción: Error al procesar el audio."))

    def mostrar_qr(self, record_id, profesor, materia, transcripcion, fecha):
        top = ctk.CTkToplevel(self)
        top.title(f"QR - Petición #{record_id}")
        top.geometry("380, 480")
        top.resizable(False, False)

        lbl_info = ctk.CTkLabel(top, text="Escanea para ver la información detallada:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_info.pack(pady=10)

        # Crear un texto estructurado y visual para el código QR
        contenido_visual = (
            f"🎓 REPORTE ACADÉMICO #{record_id}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍🏫 Profesor: {profesor}\n"
            f"📖 Materia: {materia}\n"
            f"💬 Transcripción:\n{transcripcion}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 {fecha}"
        )

        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(contenido_visual)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        temp_qr_path = "temp_qr.png"
        img.save(temp_qr_path)

        my_image = ctk.CTkImage(light_image=Image.open(temp_qr_path), dark_image=Image.open(temp_qr_path), size=(240, 240))
        
        lbl_img = ctk.CTkLabel(top, image=my_image, text="")
        lbl_img.pack(pady=5)

        lbl_preview = ctk.CTkLabel(top, text=f"Profesor: {profesor} | Materia: {materia}", font=ctk.CTkFont(size=11), text_color="gray")
        lbl_preview.pack(pady=2)

        btn_cerrar = ctk.CTkButton(top, text="Cerrar", command=top.destroy, width=100)
        btn_cerrar.pack(pady=10)

    def eliminar_peticion(self, record_id, card_widget):
        try:
            supabase.table("peticiones").delete().eq("id", record_id).execute()
            card_widget.destroy()
            if record_id in self.ids_vistos:
                self.ids_vistos.remove(record_id)
            print(f"Petición #{record_id} eliminada correctamente.")
        except Exception as e:
            print("Error al eliminar la petición:", e)

if __name__ == "__main__":
    app = AppEscritorio()
    app.mainloop()