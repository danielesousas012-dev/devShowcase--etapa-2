# DevShowcase API — etapa 2

Continuação da API da primeira etapa. Modelos: perfil, tecnologia, projeto e avaliação. Documentação interativa em `/docs`.

## Rodar localmente

Use Python 3.11 ou superior. No Windows, dentro da pasta do projeto:

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py -m uvicorn main:app --reload
```

Abra `http://127.0.0.1:8000/docs`. Sem `DATABASE_URL`, usa `devshowcase.db` (SQLite). A primeira execução atualiza as colunas `rating` e `average_rating` de um banco da etapa anterior. Faça uma cópia do banco antes de atualizar.

## Rotas

| Método | Rota | Função |
| --- | --- | --- |
| POST | `/api/profiles` | Cadastrar perfil |
| GET | `/api/profiles/{profile_id}` | Buscar perfil |
| POST | `/api/technologies` | Cadastrar tecnologia |
| GET | `/api/technologies` | Listar tecnologias |
| POST | `/api/projects` | Cadastrar projeto |
| GET | `/api/projects?technology_id=1&page=1&page_size=10` | Filtrar e paginar projetos |
| PUT | `/api/projects/{project_id}/technologies` | Acrescentar tecnologias sem repetir as já ligadas |
| POST | `/api/projects/{project_id}/feedbacks` | Dar nota de 1 a 5 com comentário; recalcula a média |

### Exemplos para demonstrar

Crie perfil e tecnologia como na etapa 1, anote os IDs retornados, e crie um projeto com eles. Use o `id` do projeto retornado nas rotas novas:

**PUT** `/api/projects/1/technologies`:

```json
{"technology_ids": [1]}
```

**POST** `/api/projects/1/feedbacks`:

```json
{"author": "Daniele Sousa", "comment": "Funcionou bem", "rating": 5}
```

Cadastre outra avaliação com nota 3 e veja `average_rating: 4.0` em GET `/api/projects`. Para o erro 404, busque `/api/profiles/99999`. Para o erro 400, tente nota 6 na rota de avaliações. O formato é `{"error":{"code":400,"message":"Dados inválidos","details":[...]}}`.

