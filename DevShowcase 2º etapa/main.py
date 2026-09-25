import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import Column, ForeignKey, Integer, String, Table, create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


project_technology = Table(
    "project_technology",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
    Column("technology_id", ForeignKey("technologies.id"), primary_key=True),
)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str] = mapped_column(String(500), default="")
    github_url: Mapped[str] = mapped_column(String(300))
    projects: Mapped[list["Project"]] = relationship(back_populates="profile")


class Technology(Base):
    __tablename__ = "technologies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    projects: Mapped[list["Project"]] = relationship(secondary=project_technology, back_populates="technologies")


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(String(1000))
    repository_url: Mapped[str] = mapped_column(String(300))
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    profile: Mapped[Profile] = relationship(back_populates="projects")
    technologies: Mapped[list[Technology]] = relationship(secondary=project_technology, back_populates="projects")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="project")
    average_rating: Mapped[float | None] = mapped_column(default=None, nullable=True)


class Feedback(Base):
    __tablename__ = "feedbacks"
    id: Mapped[int] = mapped_column(primary_key=True)
    author: Mapped[str] = mapped_column(String(120))
    comment: Mapped[str] = mapped_column(String(1000))
    rating: Mapped[int] = mapped_column(Integer)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    project: Mapped[Project] = relationship(back_populates="feedbacks")


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    bio: str = Field(default="", max_length=500)
    github_url: HttpUrl


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    bio: str
    github_url: str


class TechnologyIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TechnologyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1, max_length=1000)
    repository_url: HttpUrl
    profile_id: int = Field(gt=0)
    technology_ids: list[int] = Field(default_factory=list)


class ProjectOut(BaseModel):
    id: int
    title: str
    description: str
    repository_url: str
    profile_id: int
    technology_ids: list[int]
    average_rating: float | None


class FeedbackIn(BaseModel):
    author: str = Field(min_length=1, max_length=120)
    comment: str = Field(min_length=1, max_length=1000)
    rating: int = Field(ge=1, le=5)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author: str
    comment: str
    rating: int
    project_id: int


class TechnologyIdsIn(BaseModel):
    technology_ids: list[int] = Field(min_length=1)


class PaginatedProjects(BaseModel):
    items: list[ProjectOut]
    total: int
    page: int
    page_size: int
    pages: int


database_url = os.getenv("DATABASE_URL", "sqlite:///./devshowcase.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    # Atualização simples dos bancos SQLite criados na primeira etapa.
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "average_rating" not in {col["name"] for col in inspector.get_columns("projects")}:
            connection.execute(text("ALTER TABLE projects ADD COLUMN average_rating FLOAT"))
        if "rating" not in {col["name"] for col in inspector.get_columns("feedbacks")}:
            connection.execute(text("ALTER TABLE feedbacks ADD COLUMN rating INTEGER"))
    yield


app = FastAPI(title="DevShowcase API", version="2.0.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.status_code, "message": exc.detail}})


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(map(str, error["loc"])), "message": error["msg"]} for error in exc.errors()]
    return JSONResponse(status_code=400, content={"error": {"code": 400, "message": "Dados inválidos", "details": details}})


def get_db():
    with SessionLocal() as db:
        yield db


Db = Annotated[Session, Depends(get_db)]


@app.post("/api/profiles", response_model=ProfileOut, status_code=201)
def create_profile(data: ProfileIn, db: Db):
    profile = Profile(name=data.name, bio=data.bio, github_url=str(data.github_url))
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, db: Db):
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(404, "Perfil não encontrado")
    return profile


@app.post("/api/technologies", response_model=TechnologyOut, status_code=201)
def create_technology(data: TechnologyIn, db: Db):
    technology = Technology(name=data.name)
    db.add(technology)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tecnologia já cadastrada")
    db.refresh(technology)
    return technology


@app.get("/api/technologies", response_model=list[TechnologyOut])
def list_technologies(db: Db):
    return db.scalars(select(Technology).order_by(Technology.id)).all()


@app.post("/api/projects", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectIn, db: Db):
    if db.get(Profile, data.profile_id) is None:
        raise HTTPException(404, "Perfil não encontrado")
    technologies = resolve_technologies(db, data.technology_ids)
    project = Project(title=data.title, description=data.description,
                      repository_url=str(data.repository_url), profile_id=data.profile_id,
                      technologies=technologies)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_response(project)


def project_response(project: Project) -> ProjectOut:
    return ProjectOut(id=project.id, title=project.title, description=project.description,
                      repository_url=project.repository_url, profile_id=project.profile_id,
                      technology_ids=sorted(tech.id for tech in project.technologies),
                      average_rating=project.average_rating)


def resolve_technologies(db: Session, ids: list[int]) -> list[Technology]:
    if len(ids) != len(set(ids)) or any(id_ <= 0 for id_ in ids):
        raise HTTPException(400, "Informe IDs positivos e sem repetição")
    technologies = db.scalars(select(Technology).where(Technology.id.in_(ids))).all() if ids else []
    if len(technologies) != len(ids):
        raise HTTPException(404, "Uma ou mais tecnologias não foram encontradas")
    return technologies


@app.get("/api/projects", response_model=PaginatedProjects)
def list_projects(db: Db, technology_id: int | None = Query(None, gt=0),
                  page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    query = select(Project)
    if technology_id is not None:
        query = query.where(Project.technologies.any(Technology.id == technology_id))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    projects = db.scalars(query.order_by(Project.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedProjects(items=[project_response(project) for project in projects], total=total,
                             page=page, page_size=page_size, pages=(total + page_size - 1) // page_size)


@app.put("/api/projects/{project_id}/technologies", response_model=ProjectOut)
def add_project_technologies(project_id: int, data: TechnologyIdsIn, db: Db):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Projeto não encontrado")
    technologies = resolve_technologies(db, data.technology_ids)
    existing = {tech.id for tech in project.technologies}
    project.technologies.extend(tech for tech in technologies if tech.id not in existing)
    db.commit()
    db.refresh(project)
    return project_response(project)


@app.post("/api/projects/{project_id}/feedbacks", response_model=FeedbackOut, status_code=201)
def create_feedback(project_id: int, data: FeedbackIn, db: Db):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Projeto não encontrado")
    feedback = Feedback(project_id=project_id, author=data.author, comment=data.comment, rating=data.rating)
    db.add(feedback)
    db.flush()
    project.average_rating = float(db.scalar(select(func.avg(Feedback.rating)).where(Feedback.project_id == project_id)))
    db.commit()
    db.refresh(feedback)
    return feedback
