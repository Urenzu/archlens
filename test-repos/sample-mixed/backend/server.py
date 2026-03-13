import fastapi
import uvicorn
from backend.routes import users
from backend.services.auth import create_token, verify_token

app = fastapi.FastAPI(title="Sample API")

app.include_router(users.router, prefix="/users")


def startup():
    print("Server starting")
    configure_middleware(app)
    configure_cors(app)


def configure_middleware(application):
    application.add_middleware(
        fastapi.middleware.cors.CORSMiddleware,
        allow_origins=["*"],
    )


def configure_cors(application):
    application.add_middleware(
        fastapi.middleware.trustedhost.TrustedHostMiddleware,
        allowed_hosts=["*"],
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/auth/login")
def login(email: str, password: str):
    token = create_token(email)
    return {"token": token}


@app.get("/auth/verify")
def verify(token: str):
    payload = verify_token(token)
    return {"valid": payload is not None}


if __name__ == "__main__":
    startup()
    uvicorn.run(app, host="0.0.0.0", port=8000)
