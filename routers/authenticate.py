from fastapi import APIRouter,Depends
from fastapi.security import OAuth2PasswordRequestForm
import schemas,database as d_b
from typing import Annotated
from repository import authenticate as repo_auth

router=APIRouter(
    tags=["Login or Signup"]
)

@router.post('/signup')
def signup(user:schemas.UserSignup,db:d_b.SessionDep)->schemas.ShowUser:
    return repo_auth.signup(user,db)

@router.post('/login')
def signin(user:Annotated[OAuth2PasswordRequestForm,Depends()],db:d_b.SessionDep):
    return repo_auth.signin(user,db)
