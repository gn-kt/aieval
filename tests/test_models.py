from models import User
from database import Base


class TestUserModel:
    def test_table_name_is_users(self):
        assert User.__tablename__ == "users"

    async def test_insert_sets_id(self, db_session):
        user = User(username="test", email="test@test.com", hashed_password="hash")
        db_session.add(user)
        await db_session.commit()
        assert user.id is not None
        assert isinstance(user.id, int)

    async def test_api_key_auto_generated(self, db_session):
        user = User(username="k1", email="k1@t.com", hashed_password="x")
        db_session.add(user)
        await db_session.commit()
        assert user.api_key is not None
        assert len(user.api_key) == 32

    async def test_is_active_defaults_to_true(self, db_session):
        user = User(username="a1", email="a1@t.com", hashed_password="x")
        db_session.add(user)
        await db_session.commit()
        assert user.is_active is True

    async def test_created_at_is_set(self, db_session):
        user = User(username="c1", email="c1@t.com", hashed_password="x")
        db_session.add(user)
        await db_session.commit()
        assert user.created_at is not None

    async def test_username_unique_constraint(self, db_session):
        u1 = User(username="same", email="u1@t.com", hashed_password="x")
        u2 = User(username="same", email="u2@t.com", hashed_password="y")
        db_session.add(u1)
        await db_session.commit()
        db_session.add(u2)
        import sqlalchemy.exc
        with __import__("pytest").raises(sqlalchemy.exc.IntegrityError):
            await db_session.commit()
