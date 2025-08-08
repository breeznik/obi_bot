# tasks.py
from invoke import task

@task
def run(c):
    c.run("uvicorn app:app --reload")

