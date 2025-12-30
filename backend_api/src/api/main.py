from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Allowed status values for a task."""

    pending = "pending"
    completed = "completed"


class TaskBase(BaseModel):
    """Shared fields for task payloads."""

    title: str = Field(..., min_length=1, description="Short task title.")
    description: str = Field(..., description="Task details/notes.")
    status: TaskStatus = Field(..., description="Task status: pending|completed.")


class TaskCreate(TaskBase):
    """Request model for creating a task."""

    pass


class TaskUpdate(TaskBase):
    """Request model for full task replacement (PUT)."""

    pass


class TaskPatch(BaseModel):
    """Request model for partial task updates (PATCH)."""

    title: Optional[str] = Field(None, min_length=1, description="Short task title.")
    description: Optional[str] = Field(None, description="Task details/notes.")
    status: Optional[TaskStatus] = Field(
        None, description="Task status: pending|completed."
    )


class Task(TaskBase):
    """Response model for a task."""

    id: int = Field(..., ge=1, description="Auto-increment integer task id.")


class TaskList(BaseModel):
    """Response model for listing tasks."""

    tasks: List[Task] = Field(..., description="All tasks.")


app = FastAPI(
    title="Simple To-Do List API",
    description="Backend API for managing to-do tasks (in-memory).",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Service readiness/health endpoints."},
        {"name": "tasks", "description": "CRUD operations for tasks."},
    ],
)

# Permissive CORS for local development and simple integration.
# (Allowing '*' aligns with the user's instruction to keep it permissive for localhost dev.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (process-local). Resets on restart.
_TASKS: Dict[int, Task] = {}
_NEXT_ID: int = 1


def _get_task_or_404(task_id: int) -> Task:
    """Fetch task or raise 404 if not found."""
    task = _TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# PUBLIC_INTERFACE
@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Readiness endpoint used by clients and deployment checks.",
)
def health_check() -> Dict[str, str]:
    """Health check endpoint.

    Returns:
        A small JSON message indicating the service is running.
    """
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.get(
    "/tasks",
    response_model=TaskList,
    tags=["tasks"],
    summary="List tasks",
    description="Return all tasks currently stored in memory.",
)
def list_tasks() -> TaskList:
    """List all tasks.

    Returns:
        TaskList containing all tasks.
    """
    # Keep ordering stable by id ascending.
    tasks = sorted(_TASKS.values(), key=lambda t: t.id)
    return TaskList(tasks=tasks)


# PUBLIC_INTERFACE
@app.post(
    "/tasks",
    response_model=Task,
    status_code=201,
    tags=["tasks"],
    summary="Create task",
    description="Create a new task with an auto-incrementing integer ID.",
)
def create_task(payload: TaskCreate) -> Task:
    """Create a new task.

    Args:
        payload: TaskCreate request body.

    Returns:
        The created Task (including its new id).
    """
    global _NEXT_ID

    # Pydantic already validates required fields and enum values.
    # Keep an explicit safety guard to meet the "return 400 for invalid data" requirement
    # even if future changes bypass Pydantic.
    if payload.title.strip() == "":
        raise HTTPException(status_code=400, detail="title must not be empty")

    task = Task(id=_NEXT_ID, **payload.model_dump())
    _TASKS[_NEXT_ID] = task
    _NEXT_ID += 1
    return task


# PUBLIC_INTERFACE
@app.get(
    "/tasks/{id}",
    response_model=Task,
    tags=["tasks"],
    summary="Get task",
    description="Fetch a task by its id.",
)
def get_task(
    id: int = Path(..., ge=1, description="Task id"),
) -> Task:
    """Get a task by id.

    Args:
        id: Task id.

    Returns:
        The matching Task.

    Raises:
        HTTPException(404): If the task does not exist.
    """
    return _get_task_or_404(id)


# PUBLIC_INTERFACE
@app.put(
    "/tasks/{id}",
    response_model=Task,
    tags=["tasks"],
    summary="Update task",
    description="Replace the entire task (title, description, status).",
)
def update_task(
    payload: TaskUpdate,
    id: int = Path(..., ge=1, description="Task id"),
) -> Task:
    """Fully update a task (replace all fields).

    Args:
        payload: TaskUpdate request body.
        id: Task id.

    Returns:
        Updated Task.

    Raises:
        HTTPException(404): If the task does not exist.
        HTTPException(400): If invalid data is provided.
    """
    _get_task_or_404(id)

    if payload.title.strip() == "":
        raise HTTPException(status_code=400, detail="title must not be empty")

    updated = Task(id=id, **payload.model_dump())
    _TASKS[id] = updated
    return updated


# PUBLIC_INTERFACE
@app.patch(
    "/tasks/{id}",
    response_model=Task,
    tags=["tasks"],
    summary="Patch task",
    description="Partially update a task with any subset of fields.",
)
def patch_task(
    payload: TaskPatch,
    id: int = Path(..., ge=1, description="Task id"),
) -> Task:
    """Partially update a task.

    Args:
        payload: TaskPatch request body (any subset of fields).
        id: Task id.

    Returns:
        Updated Task.

    Raises:
        HTTPException(404): If the task does not exist.
        HTTPException(400): If invalid data is provided (e.g., empty title).
    """
    existing = _get_task_or_404(id)
    patch_data: Dict[str, Any] = payload.model_dump(exclude_unset=True)

    if "title" in patch_data and patch_data["title"] is not None:
        if patch_data["title"].strip() == "":
            raise HTTPException(status_code=400, detail="title must not be empty")

    new_data = existing.model_dump()
    new_data.update(patch_data)

    updated = Task(**new_data)
    _TASKS[id] = updated
    return updated


# PUBLIC_INTERFACE
@app.delete(
    "/tasks/{id}",
    status_code=204,
    tags=["tasks"],
    summary="Delete task",
    description="Delete a task by id.",
)
def delete_task(
    id: int = Path(..., ge=1, description="Task id"),
) -> None:
    """Delete a task.

    Args:
        id: Task id.

    Raises:
        HTTPException(404): If the task does not exist.
    """
    _get_task_or_404(id)
    del _TASKS[id]
    return None
