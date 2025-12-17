# API Manager Dashboard Backend

Esta API é um backend RESTful desenvolvido com **FastAPI** que atua como um gateway para o **Supabase**. Ela gerencia o cadastro de Cidades, Categorias, Serviços e Usuários, incluindo manipulação de arquivos (imagens) via Supabase Storage.

## Tecnologias Utilizadas

- **Linguagem:** Python 3.x
    
- **Framework:** FastAPI
    
- **HTTP Client Assíncrono:** aiohttp
    
- **Banco de Dados & Storage:** Supabase (via API REST)
    
- **Servidor:** Uvicorn
    

## Configuração e Instalação

### Pré-requisitos

Certifique-se de ter as seguintes variáveis de ambiente configuradas em um arquivo `.env` na raiz do projeto:

Fragmento do código

```
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sua-chave-secreta-service-role
PORT=8000
```

> **Nota:** A API utiliza a `SERVICE_ROLE_KEY` para ter permissões administrativas no Supabase (bypassing RLS se necessário), portanto, mantenha essa chave segura.

### Buckets do Storage

Para que o upload de imagens funcione, crie os seguintes buckets públicos no Supabase Storage:

- `logos` (para logotipos de serviços)
    
- `avatars` (para fotos de perfil de usuários)
    

---

## Modelos de Dados (Schemas)

### City (Cidade)

| **Campo** | **Tipo** | **Obrigatório** | **Descrição**           |
| --------- | -------- | --------------- | ----------------------- |
| `name`    | string   | Sim             | Nome da cidade          |
| `state`   | string   | Sim             | Sigla ou nome do estado |

### Category (Categoria)

| **Campo** | **Tipo** | **Obrigatório** | **Descrição**     |
| --------- | -------- | --------------- | ----------------- |
| `name`    | string   | Sim             | Nome da categoria |

### Service (Serviço)

| **Campo**     | **Tipo** | **Obrigatório** | **Descrição**                    |
| ------------- | -------- | --------------- | -------------------------------- |
| `name`        | string   | Sim             | Nome do serviço                  |
| `description` | string   | Não             | Detalhes do serviço              |
| `city_id`     | int      | Sim             | ID da cidade associada           |
| `category_id` | int      | Sim             | ID da categoria associada        |
| `logo_url`    | string   | Automático      | URL da imagem (gerado no upload) |

### User (Usuário)

| **Campo**    | **Tipo** | **Obrigatório** | **Descrição**                  |
| ------------ | -------- | --------------- | ------------------------------ |
| `name`       | string   | Sim             | Nome do usuário                |
| `email`      | string   | Sim             | E-mail do usuário (único)      |
| `avatar_url` | string   | Automático      | URL da foto (gerado no upload) |

---

## Endpoints da API

### Geral

- **GET** `/`
    
    - Retorna o status da API e um mapa de todos os endpoints disponíveis.
        

### 🏙️ Cidades (`/cities`)

| **Método** | **Endpoint**   | **Descrição**            | **Payload (Body)**                                     |
| ---------- | -------------- | ------------------------ | ------------------------------------------------------ |
| `GET`      | `/cities`      | Lista todas as cidades   | N/A                                                    |
| `GET`      | `/cities/{id}` | Busca uma cidade por ID  | N/A                                                    |
| `POST`     | `/cities`      | Cria uma nova cidade     | `{ "name": "...", "state": "..." }`                    |
| `PUT`      | `/cities/{id}` | Atualiza dados da cidade | `{ "name": "...", "state": "..." }` (campos opcionais) |
| `DELETE`   | `/cities/{id}` | Remove uma cidade        | N/A                                                    |

> _Nota: Não é possível deletar cidades que possuam serviços vinculados._

### Categorias (`/categories`)

| **Método** | **Endpoint**       | **Descrição**             | **Payload (Body)**  |
| ---------- | ------------------ | ------------------------- | ------------------- |
| `GET`      | `/categories`      | Lista todas as categorias | N/A                 |
| `GET`      | `/categories/{id}` | Busca categoria por ID    | N/A                 |
| `POST`     | `/categories`      | Cria nova categoria       | `{ "name": "..." }` |
| `PUT`      | `/categories/{id}` | Atualiza categoria        | `{ "name": "..." }` |
| `DELETE`   | `/categories/{id}` | Remove uma categoria      | N/A                 |

> _Nota: Não é possível deletar categorias que possuam serviços vinculados._

### Serviços (`/services`)

| **Método** | **Endpoint**     | **Descrição**                        | **Parâmetros / Body**                        |
| ---------- | ---------------- | ------------------------------------ | -------------------------------------------- |
| `GET`      | `/services`      | Lista serviços (com relacionamentos) | Query Params: `?city_id=1&category_id=2`     |
| `GET`      | `/services/{id}` | Busca serviço por ID                 | N/A                                          |
| `POST`     | `/services`      | Cria novo serviço                    | JSON conforme Schema `Service`               |
| `PUT`      | `/services/{id}` | Atualiza serviço                     | JSON parcial do Schema `Service`             |
| `DELETE`   | `/services/{id}` | Remove serviço                       | N/A (Remove logo do storage automaticamente) |

#### Upload de Logo de Serviço

- **POST** `/services/{id}/logo`
    
    - **Body:** `form-data` com campo `file`.
        
    - **Restrições:** Máximo 5MB.
        
    - **Ação:** Faz upload para o bucket `logos` e atualiza a URL no banco.
        
- **DELETE** `/services/{id}/logo`
    
    - Remove a imagem do storage e limpa o campo no banco.
        

### Usuários (`/users`)

| **Método** | **Endpoint**  | **Descrição**        | **Payload (Body)**                             |
| ---------- | ------------- | -------------------- | ---------------------------------------------- |
| `GET`      | `/users`      | Lista todos usuários | N/A                                            |
| `GET`      | `/users/{id}` | Busca usuário por ID | N/A                                            |
| `POST`     | `/users`      | Cria novo usuário    | `{ "name": "...", "email": "..." }`            |
| `PUT`      | `/users/{id}` | Atualiza usuário     | `{ "name": "...", "email": "..." }`            |
| `DELETE`   | `/users/{id}` | Remove usuário       | N/A (Remove avatar do storage automaticamente) |

#### Upload de Avatar de Usuário

- **POST** `/users/{id}/avatar`
    
    - **Body:** `form-data` com campo `file`.
        
    - **Restrições:** Máximo 5MB.
        
    - **Ação:** Faz upload para o bucket `avatars` e atualiza a URL no banco.
        
- **DELETE** `/users/{id}/avatar`
    
    - Remove a imagem do storage e limpa o campo no banco.
        

---

## Tratamento de Erros

A API retorna códigos de status HTTP padrão:

- `200 OK`: Sucesso.
    
- `201 Created`: Recurso criado com sucesso.
    
- `400 Bad Request`: Erro de validação (ex: e-mail duplicado, arquivo muito grande, violação de chave estrangeira).
    
- `404 Not Found`: Recurso (ID) não encontrado.
    
- `500 Internal Server Error`: Erro de conexão com o Supabase ou falha interna.
    

## Integração com Supabase

A API não utiliza a biblioteca cliente oficial do Supabase (`supabase-py`), mas sim chamadas HTTP diretas via `aiohttp` para os endpoints REST (`/rest/v1/...`) e Storage (`/storage/v1/...`).

- **Autenticação:** Todas as requisições ao Supabase incluem os headers `apikey` e `Authorization: Bearer` configurados via variáveis de ambiente.
    
- **Escrita:** Métodos `POST` e `PATCH` utilizam o header `Prefer: return=representation` para retornar o objeto atualizado/criado na resposta.
