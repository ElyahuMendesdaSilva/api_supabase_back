from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from typing import Optional
import uuid
import aiohttp

load_dotenv()

app = FastAPI()

# Configurar CORS CORRETAMENTE
# Adicione TODAS as origens que podem acessar sua API
origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8000",
    "https://alexdoidopormoney.netlify.app/",  # SEU SITE NETLIFY
    "https://*.netlify.app",                  # Qualquer subdomínio Netlify
    "https://api-supabase-back.onrender.com/", # Seu próprio backend
]

# NO LUGAR DA CONFIGURAÇÃO ATUAL DE CORS, USE:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite TODAS as origens (apenas para teste)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurações do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Verificar se variáveis de ambiente estão definidas
if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️  AVISO: Variáveis de ambiente SUPABASE_URL ou SUPABASE_KEY não definidas!")

# Headers para todas as requisições
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# -------- MODELS --------
class CityIn(BaseModel):
    name: str
    state: str

class CategoryIn(BaseModel):
    name: str

class ServiceIn(BaseModel):
    name: str
    description: Optional[str] = None
    city_id: int
    category_id: int

class UserIn(BaseModel):
    name: str
    email: str

# -------- FUNÇÕES AUXILIARES --------
async def supabase_request(method: str, table: str, data: dict = None, filters: dict = None, select: str = "*"):
    """Faz requisições para a API REST do Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    # Adiciona parâmetros de filtro
    if filters:
        filter_str = "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
        url += f"?{filter_str}"
    
    # Adiciona select
    if "?" in url:
        url += f"&select={select}"
    else:
        url += f"?select={select}"
    
    async with aiohttp.ClientSession() as session:
        kwargs = {"headers": HEADERS}
        if data and method in ["POST", "PATCH"]:
            kwargs["json"] = data
        
        try:
            if method == "GET":
                async with session.get(url, **kwargs) as response:
                    return await response.json()
            elif method == "POST":
                async with session.post(url, **kwargs) as response:
                    return await response.json()
            elif method == "PATCH":
                async with session.patch(url, **kwargs) as response:
                    return await response.json()
            elif method == "DELETE":
                async with session.delete(url, **kwargs) as response:
                    return await response.text()
        except Exception as e:
            raise Exception(f"Erro na requisição Supabase: {str(e)}")

async def upload_to_storage(bucket: str, filename: str, file_content: bytes):
    """Faz upload de arquivo para o Supabase Storage"""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url,
                headers=headers,
                data=file_content
            ) as response:
                if response.status == 200:
                    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
                else:
                    error_text = await response.text()
                    raise Exception(f"Upload falhou: {response.status} - {error_text}")
        except Exception as e:
            raise Exception(f"Erro ao conectar com Supabase Storage: {str(e)}")

# -------- ROTAS --------
@app.get("/cities")
async def list_cities():
    data = await supabase_request("GET", "cities")
    return data or []

@app.post("/cities")
async def create_city(city: CityIn):
    try:
        data = await supabase_request("POST", "cities", city.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar cidade: {str(e)}")

@app.get("/categories")
async def list_categories():
    data = await supabase_request("GET", "categories")
    return data or []

@app.post("/categories")
async def create_category(category: CategoryIn):
    try:
        data = await supabase_request("POST", "categories", category.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar categoria: {str(e)}")

@app.get("/services")
async def list_services():
    try:
        data = await supabase_request("GET", "services", select="*,cities(name,state),categories(name)")
        return data or []
    except Exception as e:
        raise HTTPException(500, f"Erro ao listar serviços: {str(e)}")

@app.post("/services")
async def create_service(service: ServiceIn):
    try:
        data = await supabase_request("POST", "services", service.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar serviço: {str(e)}")

@app.post("/services/{service_id}/logo")
async def upload_service_logo(service_id: int, file: UploadFile = File(...)):
    try:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(400, "Arquivo muito grande (max 5MB)")
        
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
        unique_filename = f"service_{service_id}_{uuid.uuid4()}.{file_extension}"
        
        logo_url = await upload_to_storage("logos", unique_filename, content)
        await supabase_request("PATCH", "services", {"logo_url": logo_url}, {"id": service_id})
        
        return {"logo_url": logo_url, "message": "Logo enviado com sucesso"}
    except Exception as e:
        raise HTTPException(500, f"Erro ao fazer upload: {str(e)}")

@app.get("/users")
async def list_users():
    data = await supabase_request("GET", "users")
    return data or []

@app.post("/users")
async def create_user(user: UserIn):
    try:
        data = await supabase_request("POST", "users", user.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar usuário: {str(e)}")

@app.post("/users/{user_id}/avatar")
async def upload_user_avatar(user_id: int, file: UploadFile = File(...)):
    try:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(400, "Arquivo muito grande (max 5MB)")
        
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
        unique_filename = f"user_{user_id}_{uuid.uuid4()}.{file_extension}"
        
        avatar_url = await upload_to_storage("avatars", unique_filename, content)
        await supabase_request("PATCH", "users", {"avatar_url": avatar_url}, {"id": user_id})
        
        return {"avatar_url": avatar_url, "message": "Avatar enviado com sucesso"}
    except Exception as e:
        raise HTTPException(500, f"Erro ao fazer upload: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "API Manager Dashboard Backend",
        "status": "online",
        "cors_allowed_origins": [
            "https://alexdoidopormoney.netlify.app",
            "https://*.netlify.app"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

