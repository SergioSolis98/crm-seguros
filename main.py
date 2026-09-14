from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
import os

# Configuración de base de datos
DATABASE_URL = "sqlite:///./crm_seguros.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de datos
class ProspectoDB(Base):
    __tablename__ = "prospectos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    telefono = Column(String(20), nullable=False)
    email = Column(String(100), nullable=True)
    ramo = Column(String(50), nullable=False)
    notas = Column(Text, nullable=True)
    fecha_seguimiento = Column(DateTime, nullable=False)
    estado = Column(String(20), default="Pendiente")
    creado_en = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Esquemas de validación
class ProspectoCreate(BaseModel):
    nombre: str
    telefono: str
    email: str | None = None
    ramo: str
    notas: str | None = None
    fecha_seguimiento: datetime

class ProspectoResponse(ProspectoCreate):
    id: int
    estado: str
    creado_en: datetime

    class Config:
        from_attributes = True

# Inicializar API
app = FastAPI(title="CRM Seguros")

# Servir archivos estáticos (Frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_notificacion(nombre: str, telefono: str, ramo: str, fecha: datetime):
    # Aquí puedes conectar un webhook a WhatsApp, Telegram o correo SMTP
    print(f"\n[RECORDATORIO GENERADO] Contactar a {nombre} ({telefono}) para seguro de {ramo} el {fecha}\n")

# --- Rutas de la API ---

@app.get("/")
def servir_frontend():
    return FileResponse("static/index.html")

@app.post("/api/prospectos/", response_model=ProspectoResponse)
def crear_prospecto(data: ProspectoCreate, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    nuevo = ProspectoDB(**data.dict())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    bg_tasks.add_task(log_notificacion, nuevo.nombre, nuevo.telefono, nuevo.ramo, nuevo.fecha_seguimiento)
    return nuevo

@app.get("/api/prospectos/", response_model=list[ProspectoResponse])
def obtener_prospectos(estado: str | None = None, db: Session = Depends(get_db)):
    query = db.query(ProspectoDB)
    if estado and estado != "Todos":
        query = query.filter(ProspectoDB.estado == estado)
    return query.order_by(ProspectoDB.fecha_seguimiento.asc()).all()

@app.patch("/api/prospectos/{id}/completar")
def marcar_completado(id: int, db: Session = Depends(get_db)):
    prospecto = db.query(ProspectoDB).filter(ProspectoDB.id == id).first()
    if not prospecto:
        raise HTTPException(status_code=404, detail="No encontrado")
    prospecto.estado = "Completado"
    db.commit()
    return {"status": "ok"}

@app.delete("/api/prospectos/{id}")
def eliminar_uno(id: int, db: Session = Depends(get_db)):
    prospecto = db.query(ProspectoDB).filter(ProspectoDB.id == id).first()
    if not prospecto:
        raise HTTPException(status_code=404, detail="No encontrado")
    db.delete(prospecto)
    db.commit()
    return {"status": "eliminado"}

@app.delete("/api/prospectos/limpiar/completados")
def purgar_completados(db: Session = Depends(get_db)):
    afectados = db.query(ProspectoDB).filter(ProspectoDB.estado == "Completado").delete()
    db.commit()
    return {"eliminados": afectados}