from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from db import engine
from service import StudentService
from repository import StudentRepository
from exceptions import StudentError

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


# ── 依赖注入：每次请求准备一个 service ───────────────────────
def get_session() -> Session:
    # ⚠️ 关键：必须手动 commit / rollback。
    # 若用 `with Session(engine) as session: yield session`，
    # 请求结束时 session.close() 会丢弃所有未 commit 的写入 → POST 数据丢失。
    session = Session(engine)
    try:
        yield session
        session.commit()                 # 请求正常结束 → 提交
    except Exception:
        session.rollback()               # 任何异常（含 StudentError）→ 回滚
        raise                            # 异常继续往上抛，交给 exception_handler
    finally:
        session.close()


def get_service(session: Session = Depends(get_session)) -> StudentService:
    return StudentService(StudentRepository(session))


# ── 异常映射：StudentError → 404，注册一次全局生效 ───────────
@app.exception_handler(StudentError)
async def student_error_handler(request: Request, exc: StudentError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


# ── 路由 ──────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"msg": "ok"}


@app.get("/students", response_model=list[StudentOut])
def list_students(service: StudentService = Depends(get_service)):
    return service.list_all()


@app.post("/students", response_model=StudentOut, status_code=201)
def create_student(payload: StudentCreate,
                   service: StudentService = Depends(get_service)):
    return service.register(payload.name, payload.age, payload.grade)


@app.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: int,
                service: StudentService = Depends(get_service)):
    return service.get(student_id)


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int,
                   service: StudentService = Depends(get_service)):
    service.remove(student_id)


@app.patch("/students/{student_id}/grade", response_model=StudentOut)
def change_grade(student_id: int, body: GradeUpdate,
                 service: StudentService = Depends(get_service)):
    return service.change_grade(student_id, body.new_grade)


if __name__ == "__main__":
    # 方便直接跑：.venv\Scripts\python.exe api.py
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)