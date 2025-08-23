# tasks.py
from invoke import task

@task
def dev(c):
    """Run in development with auto-reload"""
    c.run("uvicorn app:app --reload --host 0.0.0.0 --port 8000")

@task
def prod(c):
    """Run in production mode"""
    c.run("uvicorn app:app --host 0.0.0.0 --port 8000")