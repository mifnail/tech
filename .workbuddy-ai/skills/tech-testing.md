# Skill: tech-testing — pytest Patterns & Fixtures

**Trigger:** Writing or running tests for the "Учет занятий" project.

**Project root:** `c:/Users/user/WorkBuddy AI/2026-09-13-22-13-51/tech`

## Running Tests

```bash
cd tech/
python -m pytest tests/ -v
```

Dependencies: `pip install flask pytest openpyxl`

## Test Files

| File | Coverage |
|------|----------|
| `tests/test_database.py` | Database unit tests (all public methods) |
| `tests/test_api.py` | API endpoint tests (all REST routes) |
| `tests/test_bot.py` | Telegram bot logic (process_text, polling) |
| `tests/test_maxbot.py` | MAX bot logic (process_text, reminders, vedomost) |
| `tests/test_backup.py` | Backup/restore (validation, atomic replace) |
| `tests/test_update.py` | Update checking |
| `tests/test_validate_require_schedule.py` | DB validation with schedule requirement |
| `tests/integration_test.py` | Integration scenarios (full user sessions) |

## Fixtures

### Database fixture (unit tests)
```python
@pytest.fixture
def db():
    d = Database(':memory:')
    yield d
    d.close()
```

### API client fixture (route tests)
```python
@pytest.fixture
def client():
    _api_module.app.config['TESTING'] = True
    original_db_fn = _api_module.get_db
    _db = Database(':memory:')
    _api_module.get_db = lambda: _db
    with _api_module.app.test_client() as c:
        yield c
    _db.close()
    _api_module.get_db = original_db_fn  # restore
```

## Test Patterns

### Database test
```python
class TestGroups:
    def test_add_group(self, db):
        gid = db.add_group('ИС-11')
        assert isinstance(gid, int) and gid > 0

    def test_add_group_duplicate(self, db):
        db.add_group('ИС-11')
        with pytest.raises(Exception):
            db.add_group('ИС-11')
```

### API test
```python
def test_create(self, client):
    rv = client.post('/api/groups', json={'name': 'ИС-11'})
    assert rv.status_code == 201
    assert 'id' in rv.json
```

### Bot test (with urlopen mock)
```python
def test_process_text(monkeypatch):
    db = Database(':memory:')
    # ... seed data ...
    reply = tgbot.process_text('/help', 123, db)
    assert 'Команды' in reply
    db.close()
```

## Key Rules

1. **Always use `:memory:` SQLite** — never touch the real `lessons.db`
2. **Each test gets a fresh database** — no shared state between tests
3. **Bot tests inject `urlopen`** — no real network calls
4. **API tests patch `get_db`** — return the in-memory DB instance
5. **Restore `get_db` after tests** — avoid leaking patched state
6. **Integration tests** simulate full user sessions (create group → add students → start lesson → mark grades → export)

## What to Test

When adding a new feature:
1. **Database method** — test the SQL logic directly
2. **API endpoint** — test HTTP status codes and response shape
3. **Edge cases** — empty input, duplicate names, missing fields, invalid dates
4. **Cascade behavior** — deleting a group cascades to students/subjects/lessons/grades
5. **Bot dialog** — test `process_text` for each command path

## Common Assertions

```python
# API response shapes
assert rv.status_code == 201        # created
assert rv.status_code == 200        # ok
assert rv.status_code == 400        # bad request (missing fields)
assert rv.json['ok'] is True        # mutation success

# Database queries
assert db.list_groups() == []       # empty
assert len(db.list_students(gid)) == 5  # count

# Bot replies
assert 'оценок' in reply.lower()    # grade text
assert 'привяз' in reply.lower()    # binding text
```
