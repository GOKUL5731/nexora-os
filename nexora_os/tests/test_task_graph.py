import pytest

from backend.orchestration.task_graph import GraphTask, TaskGraph


def test_only_dependency_ready_tasks_can_start():
    graph = TaskGraph()
    graph.add(GraphTask("a", "backend", "", "codex"))
    graph.add(GraphTask("b", "frontend", "", "cursor", ["a"]))
    assert [task.task_id for task in graph.ready()] == ["a"]
    with pytest.raises(ValueError):
        graph.set_state("b", "STARTED")
    graph.set_state("a", "COMPLETED")
    graph.set_state("b", "STARTED")
    assert graph.tasks["b"].state == "STARTED"


def test_dependency_cycles_are_rejected():
    graph = TaskGraph()
    graph.add(GraphTask("a", "a", "", "codex"))
    with pytest.raises(ValueError, match="Unknown task dependencies"):
        graph.add(GraphTask("b", "b", "", "cursor", ["missing"]))
