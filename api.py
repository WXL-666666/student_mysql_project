from fastapi import FastAPI, Depends, Request,Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from db import engine
from service import StudentService
from repository import StudentRepository
from exceptions import StudentError
from cache import StudentCache, make_redis_client

from dataclasses import dataclass 
app = FastAPI()


# ── 请求 / 响应契约（Pydantic）────────────────────────────────
class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    age: int = Field(ge=0, le=150)        # 跟 models 的 CheckConstraint 对齐
    grade: str = Field(min_length=1, max_length=10)


class StudentOut(BaseModel):
    id: int
    name: str
    age: int
    grade: str

    model_config = ConfigDict(from_attributes=True)  # 让它能从 ORM 对象直接读字段


class GradeUpdate(BaseModel):
    new_grade: str = Field(min_length=1, max_length=10)


@dataclass
class ServiceBundle:
    """一次请求的全套依赖：service 负责业务，session 负责在响应前提交"""
    service: StudentService
    session: Session


def get_session() -> Session:
    # ⚠️ 这里只负责 session 的「出生」和「善后」，不再负责提交。
    # 提交（commit）已经挪到写路由内部、return 之前——这样数据一定
    # 在响应发出之前落库，而不是"先回 201、再默默提交"。
    session = Session(engine)
    try:
        yield session
    except Exception:
        session.rollback()               # 任何异常（含 StudentError）→ 回滚
        raise                            # 异常继续往上抛，交给 exception_handler
    finally:
        session.close()


def get_bundle(session: Session = Depends(get_session)) -> ServiceBundle:
    """把 service 和 session 打包给写路由，路由需要同时用两者"""
    return ServiceBundle(
        service=StudentService(StudentRepository(session)),
        session=session,
    )


def get_service(session: Session = Depends(get_session)) -> StudentService:
    """只读路由用：它们不需要手动 commit"""
    return StudentService(StudentRepository(session))


# ── 依赖注入：每次请求准备一个 cache ───────────────────────
def get_cache() -> StudentCache:
    # 运行时连真实 Memurai；测试里会被 override 成 fakeredis（见 conftest）
    return StudentCache(make_redis_client())


# ── 异常映射：StudentError → 按异常自带的 status_code 返回 ───
# 例如 StudentNotFoundError=404、EmptyGradeError=422。
# 以前这里写死 404，导致"成绩不能为空"也被报成"学生不存在"。
@app.exception_handler(StudentError)
async def student_error_handler(request: Request, exc: StudentError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


# ── 路由 ──────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"msg": "ok"}


@app.get("/students", response_model=list[StudentOut])
def list_students(
    limit:int = Query(default=20,ge=1,le=100),
    offset:int = Query(default=0,ge=0),
    service: StudentService = Depends(get_service),
    ):
    students,_total = service.list_page(limit,offset)
    return students
    


@app.post("/students", response_model=StudentOut, status_code=201)
def create_student(payload: StudentCreate,
                   bundle: ServiceBundle = Depends(get_bundle)):
    student = bundle.service.register(payload.name, payload.age, payload.grade)
    bundle.session.commit()
    return student


@app.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: int,
                service: StudentService = Depends(get_service),
                cache: StudentCache = Depends(get_cache)):
    hit = cache.get(student_id)
    if hit is not None:
        return hit                          # 命中缓存，直接返回，不打 DB
    student = service.get(student_id)        # 未命中 → 查 DB
    data = {"id": student.id, "name": student.name,
            "age": student.age, "grade": student.grade}
    cache.set(data, ttl=60)                 # 回填缓存
    return data


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int,
                   bundle: ServiceBundle = Depends(get_bundle),
                   cache: StudentCache = Depends(get_cache)):
    bundle.service.remove(student_id)
    cache.delete(student_id)             # 让缓存失效，避免脏数据
    bundle.session.commit()              # ← 先提交，再返回 204


@app.patch("/students/{student_id}/grade", response_model=StudentOut)
def change_grade(student_id: int, body: GradeUpdate,
                 bundle: ServiceBundle = Depends(get_bundle),
                 cache: StudentCache = Depends(get_cache)):
    result = bundle.service.change_grade(student_id, body.new_grade)
    cache.delete(student_id)                 # 成绩变了，让缓存失效
    bundle.session.commit()                  # ← 先提交，再返回
    return result


if __name__ == "__main__":
    # 方便直接跑：.venv\Scripts\python.exe api.py
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)