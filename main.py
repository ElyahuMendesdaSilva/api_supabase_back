from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from typing import Optional
import uuid
import aiohttp
import json

load_dotenv()

app = FastAPI()

# Configurar CORS para todas as origens (para estudo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite TODAS as origens
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos
    allow_headers=["*"],  # Permite todos os headers
)

# Configurações do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Verificar se variáveis de ambiente estão definidas
if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️  AVISO: Variáveis de ambiente não definidas!")
    print(f"SUPABASE_URL: {'Definido' if SUPABASE_URL else 'Faltando'}")
    print(f"SUPABASE_KEY: {'Definido' if SUPABASE_KEY else 'Faltando'}")

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

class CityUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[str] = None

class CategoryIn(BaseModel):
    name: str

class CategoryUpdate(BaseModel):
    name: Optional[str] = None

class ServiceIn(BaseModel):
    name: str
    description: Optional[str] = None
    city_id: int
    category_id: int

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    city_id: Optional[int] = None
    category_id: Optional[int] = None

class UserIn(BaseModel):
    name: str
    email: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

# -------- FUNÇÕES AUXILIARES --------
async def supabase_request(method: str, endpoint: str = None, table: str = None, data: dict = None, 
                          filters: dict = None, select: str = "*", id: int = None):
    """Faz requisições para a API REST do Supabase"""
    
    # Construir URL
    if endpoint:
        url = f"{SUPABASE_URL}/rest/v1{endpoint}"
    elif table:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        if id:
            url += f"?id=eq.{id}"
        elif filters:
            filter_str = "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
            url += f"?{filter_str}"
        
        # Adiciona select
        if "?" in url:
            url += f"&select={select}"
        else:
            url += f"?select={select}"
    else:
        raise ValueError("Deve fornecer endpoint ou table")
    
    print(f"🌐 Requisição Supabase: {method} {url}")
    
    async with aiohttp.ClientSession() as session:
        # Cria cópia dos headers e adiciona cabeçalho Prefer para operações de escrita
        headers = HEADERS.copy()
        
        # Para POST, PATCH e DELETE, adiciona cabeçalho para retornar os dados
        if method in ["POST", "PATCH"]:
            headers["Prefer"] = "return=representation"
        elif method == "DELETE":
            headers["Prefer"] = "return=minimal"
        
        kwargs = {"headers": headers}
        if data:
            kwargs["json"] = data
        
        try:
            if method == "GET":
                async with session.get(url, **kwargs) as response:
                    print(f"✅ GET Response: {response.status}")
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"GET falhou: {response.status} - {error_text}")
                    
            elif method == "POST":
                async with session.post(url, **kwargs) as response:
                    print(f"✅ POST Response: {response.status}")
                    # Para POST, pode retornar 201 Created
                    if response.status in [200, 201]:
                        # Tenta parsear JSON, se falhar, retorna texto vazio
                        try:
                            return await response.json()
                        except:
                            # Se não houver conteúdo JSON, retorna um objeto com o status
                            return [{"id": None, "status": "created", "message": "Recurso criado com sucesso"}]
                    else:
                        error_text = await response.text()
                        raise Exception(f"POST falhou: {response.status} - {error_text}")
                    
            elif method == "PATCH":
                async with session.patch(url, **kwargs) as response:
                    print(f"✅ PATCH Response: {response.status}")
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"PATCH falhou: {response.status} - {error_text}")
                    
            elif method == "DELETE":
                async with session.delete(url, **kwargs) as response:
                    print(f"✅ DELETE Response: {response.status}")
                    if response.status in [200, 204]:
                        return {"message": "Deleted successfully"}
                    else:
                        error_text = await response.text()
                        raise Exception(f"DELETE falhou: {response.status} - {error_text}")
                    
        except Exception as e:
            print(f"❌ Erro na requisição: {str(e)}")
            # Se for erro de JSON, trata especificamente
            if "JSON" in str(e) or "decode" in str(e).lower():
                # Para POST, se deu erro de JSON mas o status era 201, assume que criou
                if method == "POST":
                    print("⚠️  Erro de parse JSON em POST, mas provavelmente criou o recurso")
                    return [{"id": None, "status": "created_no_json"}]
            raise Exception(f"Erro na requisição Supabase: {str(e)}")
        
async def upload_to_storage(bucket: str, filename: str, file_content: bytes):
    """Faz upload de arquivo para o Supabase Storage"""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    
    print(f"📤 Upload para: {bucket}/{filename}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url,
                headers=headers,
                data=file_content
            ) as response:
                if response.status == 200:
                    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
                    print(f"✅ Upload bem-sucedido: {public_url}")
                    return public_url
                else:
                    error_text = await response.text()
                    print(f"❌ Upload falhou: {response.status} - {error_text}")
                    raise Exception(f"Upload falhou: {response.status} - {error_text}")
        except Exception as e:
            print(f"❌ Erro ao conectar: {str(e)}")
            raise Exception(f"Erro ao conectar com Supabase Storage: {str(e)}")

async def delete_from_storage(bucket: str, filename: str):
    """Remove arquivo do Supabase Storage"""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    
    print(f"🗑️  Deletando: {bucket}/{filename}")
    
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                return True
            else:
                error_text = await response.text()
                print(f"❌ Falha ao deletar: {error_text}")
                return False

# -------- CIDADES --------
@app.get("/cities")
async def list_cities():
    try:
        data = await supabase_request("GET", table="cities")
        return data or []
    except Exception as e:
        raise HTTPException(500, f"Erro ao listar cidades: {str(e)}")

@app.get("/cities/{city_id}")
async def get_city(city_id: int):
    try:
        data = await supabase_request("GET", table="cities", id=city_id)
        if not data:
            raise HTTPException(404, "Cidade não encontrada")
        return data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao buscar cidade: {str(e)}")

@app.post("/cities")
async def create_city(city: CityIn):
    try:
        data = await supabase_request("POST", table="cities", data=city.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar cidade: {str(e)}")

@app.put("/cities/{city_id}")
async def update_city(city_id: int, city: CityUpdate):
    try:
        # Verifica se a cidade existe
        existing = await supabase_request("GET", table="cities", id=city_id)
        if not existing:
            raise HTTPException(404, "Cidade não encontrada")
        
        # Atualiza apenas os campos fornecidos
        update_data = {k: v for k, v in city.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(400, "Nenhum dado para atualizar")
        
        data = await supabase_request("PATCH", table="cities", data=update_data, id=city_id)
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao atualizar cidade: {str(e)}")

@app.delete("/cities/{city_id}")
async def delete_city(city_id: int):
    try:
        # Verifica se a cidade existe
        existing = await supabase_request("GET", table="cities", id=city_id)
        if not existing:
            raise HTTPException(404, "Cidade não encontrada")
        
        # Verifica se há serviços usando esta cidade
        services = await supabase_request("GET", table="services", filters={"city_id": city_id})
        if services and len(services) > 0:
            raise HTTPException(400, "Não é possível deletar cidade com serviços associados")
        
        await supabase_request("DELETE", table="cities", id=city_id)
        return {"message": "Cidade deletada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao deletar cidade: {str(e)}")

# -------- CATEGORIAS --------
@app.get("/categories")
async def list_categories():
    try:
        data = await supabase_request("GET", table="categories")
        return data or []
    except Exception as e:
        raise HTTPException(500, f"Erro ao listar categorias: {str(e)}")

@app.get("/categories/{category_id}")
async def get_category(category_id: int):
    try:
        data = await supabase_request("GET", table="categories", id=category_id)
        if not data:
            raise HTTPException(404, "Categoria não encontrada")
        return data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao buscar categoria: {str(e)}")

@app.post("/categories")
async def create_category(category: CategoryIn):
    try:
        data = await supabase_request("POST", table="categories", data=category.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar categoria: {str(e)}")

@app.put("/categories/{category_id}")
async def update_category(category_id: int, category: CategoryUpdate):
    try:
        existing = await supabase_request("GET", table="categories", id=category_id)
        if not existing:
            raise HTTPException(404, "Categoria não encontrada")
        
        update_data = {k: v for k, v in category.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(400, "Nenhum dado para atualizar")
        
        data = await supabase_request("PATCH", table="categories", data=update_data, id=category_id)
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao atualizar categoria: {str(e)}")

@app.delete("/categories/{category_id}")
async def delete_category(category_id: int):
    try:
        existing = await supabase_request("GET", table="categories", id=category_id)
        if not existing:
            raise HTTPException(404, "Categoria não encontrada")
        
        # Verifica se há serviços usando esta categoria
        services = await supabase_request("GET", table="services", filters={"category_id": category_id})
        if services and len(services) > 0:
            raise HTTPException(400, "Não é possível deletar categoria com serviços associados")
        
        await supabase_request("DELETE", table="categories", id=category_id)
        return {"message": "Categoria deletada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao deletar categoria: {str(e)}")

# -------- SERVIÇOS --------
@app.get("/services")
async def list_services(city_id: Optional[int] = Query(None), category_id: Optional[int] = Query(None)):
    try:
        filters = {}
        if city_id:
            filters["city_id"] = city_id
        if category_id:
            filters["category_id"] = category_id
        
        if filters:
            data = await supabase_request("GET", table="services", filters=filters, 
                                         select="*,cities(*),categories(*)")
        else:
            data = await supabase_request("GET", table="services", 
                                         select="*,cities(*),categories(*)")
        
        return data or []
    except Exception as e:
        raise HTTPException(500, f"Erro ao listar serviços: {str(e)}")

@app.get("/services/{service_id}")
async def get_service(service_id: int):
    try:
        data = await supabase_request("GET", table="services", id=service_id,
                                     select="*,cities(*),categories(*)")
        if not data:
            raise HTTPException(404, "Serviço não encontrado")
        return data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao buscar serviço: {str(e)}")

@app.post("/services")
async def create_service(service: ServiceIn):
    try:
        # Validação de city_id e category_id
        city = await supabase_request("GET", table="cities", id=service.city_id)
        if not city:
            raise HTTPException(400, "Cidade não encontrada")
        
        category = await supabase_request("GET", table="categories", id=service.category_id)
        if not category:
            raise HTTPException(400, "Categoria não encontrada")
        
        data = await supabase_request("POST", table="services", data=service.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar serviço: {str(e)}")

@app.put("/services/{service_id}")
async def update_service(service_id: int, service: ServiceUpdate):
    try:
        existing = await supabase_request("GET", table="services", id=service_id)
        if not existing:
            raise HTTPException(404, "Serviço não encontrado")
        
        # Validações
        if service.city_id:
            city = await supabase_request("GET", table="cities", id=service.city_id)
            if not city:
                raise HTTPException(400, "Cidade não encontrada")
        
        if service.category_id:
            category = await supabase_request("GET", table="categories", id=service.category_id)
            if not category:
                raise HTTPException(400, "Categoria não encontrada")
        
        update_data = {k: v for k, v in service.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(400, "Nenhum dado para atualizar")
        
        data = await supabase_request("PATCH", table="services", data=update_data, id=service_id)
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao atualizar serviço: {str(e)}")

@app.delete("/services/{service_id}")
async def delete_service(service_id: int):
    try:
        existing = await supabase_request("GET", table="services", id=service_id, select="logo_url")
        if not existing:
            raise HTTPException(404, "Serviço não encontrado")
        
        # Remove o logo se existir
        if existing[0].get("logo_url"):
            logo_url = existing[0]["logo_url"]
            filename = logo_url.split('/')[-1]
            await delete_from_storage("logos", filename)
        
        await supabase_request("DELETE", table="services", id=service_id)
        return {"message": "Serviço deletado com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao deletar serviço: {str(e)}")

@app.post("/services/{service_id}/logo")
async def upload_service_logo(service_id: int, file: UploadFile = File(...)):
    try:
        # Verifica se o serviço existe
        service = await supabase_request("GET", table="services", id=service_id)
        if not service:
            raise HTTPException(404, "Serviço não encontrado")
        
        # Lê o arquivo
        content = await file.read()
        
        # Verifica tamanho (max 5MB)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(400, "Arquivo muito grande (máximo 5MB)")
        
        # Gera nome único
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
        unique_filename = f"service_{service_id}_{uuid.uuid4()}.{file_extension}"
        
        # Faz upload
        logo_url = await upload_to_storage("logos", unique_filename, content)
        
        # Atualiza o serviço
        await supabase_request("PATCH", table="services", data={"logo_url": logo_url}, id=service_id)
        
        return {"logo_url": logo_url, "message": "Logo enviado com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao fazer upload: {str(e)}")

@app.delete("/services/{service_id}/logo")
async def delete_service_logo(service_id: int):
    try:
        service = await supabase_request("GET", table="services", id=service_id, select="logo_url")
        if not service:
            raise HTTPException(404, "Serviço não encontrado")
        
        logo_url = service[0].get("logo_url")
        if not logo_url:
            raise HTTPException(400, "Serviço não possui logo")
        
        # Remove do storage
        filename = logo_url.split('/')[-1]
        await delete_from_storage("logos", filename)
        
        # Atualiza o serviço
        await supabase_request("PATCH", table="services", data={"logo_url": None}, id=service_id)
        
        return {"message": "Logo removido com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao remover logo: {str(e)}")

# -------- USUÁRIOS --------
@app.get("/users")
async def list_users():
    try:
        data = await supabase_request("GET", table="users")
        return data or []
    except Exception as e:
        raise HTTPException(500, f"Erro ao listar usuários: {str(e)}")

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    try:
        data = await supabase_request("GET", table="users", id=user_id)
        if not data:
            raise HTTPException(404, "Usuário não encontrado")
        return data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao buscar usuário: {str(e)}")

@app.post("/users")
async def create_user(user: UserIn):
    try:
        # Verifica se email já existe
        existing = await supabase_request("GET", table="users", filters={"email": user.email})
        if existing and len(existing) > 0:
            raise HTTPException(400, "Email já cadastrado")
        
        data = await supabase_request("POST", table="users", data=user.dict())
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar usuário: {str(e)}")

@app.put("/users/{user_id}")
async def update_user(user_id: int, user: UserUpdate):
    try:
        existing = await supabase_request("GET", table="users", id=user_id)
        if not existing:
            raise HTTPException(404, "Usuário não encontrado")
        
        # Verifica se novo email já existe (se estiver sendo alterado)
        if user.email:
            email_check = await supabase_request("GET", table="users", filters={"email": user.email})
            if email_check and len(email_check) > 0 and email_check[0].get("id") != user_id:
                raise HTTPException(400, "Email já está em uso por outro usuário")
        
        update_data = {k: v for k, v in user.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(400, "Nenhum dado para atualizar")
        
        data = await supabase_request("PATCH", table="users", data=update_data, id=user_id)
        return data[0] if isinstance(data, list) and len(data) > 0 else data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao atualizar usuário: {str(e)}")

@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    try:
        existing = await supabase_request("GET", table="users", id=user_id, select="avatar_url")
        if not existing:
            raise HTTPException(404, "Usuário não encontrado")
        
        # Remove o avatar se existir
        if existing[0].get("avatar_url"):
            avatar_url = existing[0]["avatar_url"]
            filename = avatar_url.split('/')[-1]
            await delete_from_storage("avatars", filename)
        
        await supabase_request("DELETE", table="users", id=user_id)
        return {"message": "Usuário deletado com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao deletar usuário: {str(e)}")

@app.post("/users/{user_id}/avatar")
async def upload_user_avatar(user_id: int, file: UploadFile = File(...)):
    try:
        # Verifica se o usuário existe
        user = await supabase_request("GET", table="users", id=user_id)
        if not user:
            raise HTTPException(404, "Usuário não encontrado")
        
        # Lê o arquivo
        content = await file.read()
        
        # Verifica tamanho (max 5MB)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(400, "Arquivo muito grande (máximo 5MB)")
        
        # Gera nome único
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
        unique_filename = f"user_{user_id}_{uuid.uuid4()}.{file_extension}"
        
        # Faz upload
        avatar_url = await upload_to_storage("avatars", unique_filename, content)
        
        # Atualiza o usuário
        await supabase_request("PATCH", table="users", data={"avatar_url": avatar_url}, id=user_id)
        
        return {"avatar_url": avatar_url, "message": "Avatar enviado com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao fazer upload: {str(e)}")

@app.delete("/users/{user_id}/avatar")
async def delete_user_avatar(user_id: int):
    try:
        user = await supabase_request("GET", table="users", id=user_id, select="avatar_url")
        if not user:
            raise HTTPException(404, "Usuário não encontrado")
        
        avatar_url = user[0].get("avatar_url")
        if not avatar_url:
            raise HTTPException(400, "Usuário não possui avatar")
        
        # Remove do storage
        filename = avatar_url.split('/')[-1]
        await delete_from_storage("avatars", filename)
        
        # Atualiza o usuário
        await supabase_request("PATCH", table="users", data={"avatar_url": None}, id=user_id)
        
        return {"message": "Avatar removido com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao remover avatar: {str(e)}")

# -------- ROTA RAIZ --------
@app.get("/")
async def root():
    return {
        "message": "API Manager Dashboard Backend",
        "status": "online",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "Esta página",
            "GET /cities": "Listar cidades",
            "GET /cities/{id}": "Buscar cidade",
            "POST /cities": "Criar cidade",
            "PUT /cities/{id}": "Atualizar cidade",
            "DELETE /cities/{id}": "Deletar cidade",
            "GET /categories": "Listar categorias",
            "GET /categories/{id}": "Buscar categoria",
            "POST /categories": "Criar categoria",
            "PUT /categories/{id}": "Atualizar categoria",
            "DELETE /categories/{id}": "Deletar categoria",
            "GET /services": "Listar serviços (com filtros ?city_id=&category_id=)",
            "GET /services/{id}": "Buscar serviço",
            "POST /services": "Criar serviço",
            "PUT /services/{id}": "Atualizar serviço",
            "DELETE /services/{id}": "Deletar serviço",
            "POST /services/{id}/logo": "Upload logo",
            "DELETE /services/{id}/logo": "Remover logo",
            "GET /users": "Listar usuários",
            "GET /users/{id}": "Buscar usuário",
            "POST /users": "Criar usuário",
            "PUT /users/{id}": "Atualizar usuário",
            "DELETE /users/{id}": "Deletar usuário",
            "POST /users/{id}/avatar": "Upload avatar",
            "DELETE /users/{id}/avatar": "Remover avatar"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)

