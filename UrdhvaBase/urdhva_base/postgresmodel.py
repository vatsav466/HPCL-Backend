import json
import time
import typing
import asyncio
import pydantic
import datetime
import traceback
import urdhva_base
import urdhva_base.settings
import urdhva_base.redispool
import urdhva_base.queryparams
import urdhva_base.utilities as utils
from sqlalchemy.pool import NullPool
from starlette.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.pool import NullPool

from sqlalchemy import (
    BigInteger,
    TIMESTAMP,
    DateTime,
    func,
    Identity,
    select,
    String,
    text
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    undefer
)


# Define Base class for declarative base
class Base(MappedAsDataclass, DeclarativeBase, dataclass_callable=pydantic.dataclasses.dataclass):
    class Config:
        orm_mode = True


# Define base model for Postgresql
class UrdhvaPostgresBase(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column("id", BigInteger, autoincrement=True, primary_key=True,
                                                     init=False, server_default=Identity(minvalue=1), unique=True)
    created_at: Mapped[typing.Optional[datetime.datetime]] = mapped_column("created_at", TIMESTAMP,
                                                                           server_default=func.now(), init=False)
    updated_at: Mapped[typing.Optional[datetime.datetime]] = mapped_column("updated_at", TIMESTAMP,
                                                                           server_default=func.now(),
                                                                           onupdate=func.now(), init=False)
    entity_id: Mapped[typing.Optional[str]] = mapped_column("entity_id", String, index=True)


class DatabaseManager:
    def __init__(self, database_url):
        self.engine = create_async_engine(database_url, poolclass=NullPool)
        self.async_session = async_sessionmaker(self.engine)

    async def get_session(self):
        return self.async_session()

    async def create_all(self):
        async with self.engine.begin() as conn:
            # Sorting all tables to make sure non-dependent one should configure first
            tables = Base.metadata.sorted_tables
            await conn.run_sync(Base.metadata.create_all, tables=tables)


manager = DatabaseManager(str(urdhva_base.settings.db_urls["postgres_async"][0]))


# --------------------------------------------------------------------------------------
# Create tables (once per application)
# --------------------------------------------------------------------------------------
async def create_tables():
    await manager.create_all()


# Define base model for Pydantic
class BasePostgresModel(pydantic.BaseModel):
    __tablename__ = ""

    @classmethod
    async def cleanup_session(cls, session):
        try:
            session.rollback()
        except:
            ...
        try:
            session.close()
        except:
            ...

    @classmethod
    async def _apply_acls(cls):
        ...

    @classmethod
    async def _get_entity_id(cls, entity_id=None):
        if urdhva_base.ctx.exists():
            return urdhva_base.ctx['entity_id']
        return entity_id

    @classmethod
    async def get(cls, row_id, entity_id=None, skip_secrets=False):
        """
        For Getting specific record
        :param row_id: record id
        :param entity_id: entity id
        :return: record if exists else null
        """
        # entity_id = cls._get_entity_id(entity_id)
        # if not entity_id:
        #     raise "missing context information"
        session = await manager.get_session()
        result = await session.execute(
            select(cls.Config.schema_class).where(cls.Config.schema_class.id == int(row_id))
        )
        resp = result.scalars().first()
        await asyncio.shield(session.close())
        return resp

    @classmethod
    async def count(cls, params: urdhva_base.queryparams.QueryParams = None, entity_id=None):
        """

        :param params:
        :param entity_id:
        :return:
        """
        # entity_id = cls._get_entity_id(entity_id)
        # if not entity_id:
        #     raise "missing context information"
        query = [f"select count('*') from {cls.__tablename__}"]
        query_params = [f"{cls.__tablename__}.entity_id = '{entity_id}'"] if entity_id else []
        # todo:- need to implement this for all keys, both permitted and prohibited
        if urdhva_base.ctx.exists() and urdhva_base.context.context.get('rpt', {}):
            rpt = urdhva_base.context.context.get('rpt', {})
            key = f"access_restrictions_{urdhva_base.ctx['entity_id']}"
            redis_client = await urdhva_base.redispool.get_redis_connection()
            if await redis_client.hexists(key, rpt['email']):
                data = json.loads(await redis_client.hget(f"access_restrictions_{urdhva_base.ctx['entity_id']}",
                                                          rpt['email']))
                # todo:- Temporary fix for ACL'S
                if data.get("organizations_permitted"):
                    permitted_org = data['organizations_permitted'].split(",")
                    if len(permitted_org) == 1:
                        permitted_org = f"('{permitted_org[0]}')"
                    if cls.__tablename__ == "organization":
                        query_params.append(f"id in {permitted_org}")
                    else:
                        query_params.append(f"organization_id in {permitted_org}")
        if hasattr(cls.Config, 'standard_query'):
            query_params.append(cls.Config.standard_query)
        if params and params.q and len(params.q) > 0:
            query_params.append(params.q)
        if len(query_params):
            query.append("where " + " AND ".join(query_params))
        session = await manager.get_session()
        total = await session.scalar(text(" ".join(query)))
        await asyncio.shield(session.close())
        return total

    @classmethod
    async def update_by_query(cls, query, entity_id=None):
        session = await manager.get_session()
        try:
            result = await session.execute(text(query))
            print(f"Rows committed {result.rowcount}")
            await session.commit()
        except Exception as e:
            print(f"Exception while running update by query {e}")
            raise f"Exception while running update by query {e}"
        finally:
            await asyncio.shield(session.close())

    @classmethod
    async def get_aggr_data(cls, query, limit=100, skip=0, skip_total=True):
        """
        @Description: For getting aggregated data, Join queries
        :param query: Query string to execute
        :param limit:
        :param skip:
        :return:
        """
        # if not limit:
        #     limit = 100
        # if not skip:
        #     skip = 0
        # Generating Postgres query from given query
        session = await manager.get_session()
        try:
            if limit:
                query_ = f"{query} LIMIT {limit} OFFSET {limit * skip}"
            else:
                query_ = f"{query}"
            if not query_.upper().startswith("WITH ") and not query_.upper().startswith("SELECT "):
                query_ = f"select {query_}"
            result = await session.execute(text(query_))
            resp = result.all()
            # Getting key columns from reults
            columns = [key for key in result.keys()]
            results = [{columns[index]: value for index, value in enumerate(row)} for row in resp]
            # Fetching total available records for the given query
            total = len(results)
            if not skip_total:
                try:
                    total = await session.scalar(text(f"select COUNT(*) FROM(SELECT {query}) AS subquery"))
                except:
                    ...
            results_data = {"data": results, "count": len(results), "total": total}
            return results_data
        except Exception as e:
            print(f"Exception while running aggregation query {e}")
            raise f"Exception while running aggregation query {e}"
        finally:
            await asyncio.shield(session.close())

    @classmethod
    async def get_all(cls, params: urdhva_base.queryparams.QueryParams = None, entity_id=None, resp_type="encoded",
                      skip_secrets=False):
        """
        @Description: For getting aggregated data, Join queries
        :param params: Query Params
        :param entity_id: Entity ID, If not provided will fetch from session context
        :param resp_type: encoded/plain
        :return:
        """
        # entity_id = cls._get_entity_id(entity_id)
        # if not entity_id:
        #     raise "missing context information"

        # If empty params, configuring default params.
        if not params:
            params = urdhva_base.queryparams.QueryParams(q="", fields='["*"]', skip=0, limit=100)
        # Generating Postgres query from QueryParams

        # ******************** For Specific Fields Start ******************** #
        fields = params.fields if params and params.fields else '["*"]'
        if isinstance(fields, str):
            fields = json.loads(fields)
        if fields and "*" not in fields and "id" not in fields:
            fields.append("id")
        # ******************** For Specific Fields End ******************** #

        query = [f"select {','.join(fields)} from {cls.__tablename__}"]
        query_params = [f"{cls.__tablename__}.entity_id = '{entity_id}'"] if entity_id else []

        # todo:- need to implement this for all keys, both permitted and prohibited
        if urdhva_base.ctx.exists() and urdhva_base.context.context.get('rpt', {}):
            rpt = urdhva_base.context.context.get('rpt', {})
            key = f"access_restrictions_{urdhva_base.ctx['entity_id']}"
            redis_client = await urdhva_base.redispool.get_redis_connection()
            if await redis_client.hexists(key, rpt['email']):
                data = json.loads(await redis_client.hget(f"access_restrictions_{urdhva_base.ctx['entity_id']}",
                                                          rpt['email']))
                #todo:- Temporary fix for ACL'S
                if data.get("organizations_permitted"):
                    permitted_org = data['organizations_permitted'].split(",")
                    if len(permitted_org) == 1:
                        permitted_org = f"('{permitted_org[0]}')"
                    if cls.__tablename__ == "organization":
                        query_params.append(f"id in {permitted_org}")
                    else:
                        query_params.append(f"organization_id in {permitted_org}")
        # Incase if there was a standard_query, appending it to the base query(Queries which are mandated in
        # Specific class)

        if hasattr(cls.Config, 'standard_query'):
            query_params.append(cls.Config.standard_query)
        if params and params.q and len(params.q) > 0:
            query_params.append(params.q)
        if params and params.q:
            search_conditions = []
            if hasattr(cls.Config, 'search_fields') and cls.Config.search_fields:
                for field in cls.Config.search_fields:
                    if params.search_text:
                        search_conditions.append(f"{cls.__tablename__}.{field} ILIKE '%{params.search_text}%'")
                
                if search_conditions:
                    print("search_conditions --> ", search_conditions)
                    query_params.append(f"({' OR '.join(search_conditions)})")
        if len(query_params):
            query.append("where " + " AND ".join(query_params))

        # ******************** For Data Sorting Params Start ******************** #
        if params.sort:
            try:
                order_by = json.loads(params.sort) if isinstance(params.sort, str) else params.sort
                for key, value in order_by.items():
                    order = 'ASC' if 'asc' in value.lower() else 'DESC'  
                    query.append(f"ORDER BY {key} {order}")
                    break
            except Exception as e:
                print(f"Exception in order by {e}")
        else:
            query.append(f"ORDER BY updated_at DESC")
        # ******************** For Data Sorting Params End ******************** #

        if params.limit:
            query.append(f"LIMIT {params.limit}")
        if params.skip:
            query.append(f"OFFSET {params.skip * params.limit}")
        session = await manager.get_session()
        try:
            result = await session.scalars(select(cls.Config.schema_class).from_statement(text(" ".join(query))))
            resp = result.all()
            results = [{key: value for key, value in row.__dict__.items() if not key.startswith("_")} for row in resp]
            total = await cls.count(params, entity_id)
            results_data = {"data": results, "count": len(results), "total": total}
            if resp_type == "encoded":
                return JSONResponse(content=jsonable_encoder(results_data))
            return results_data
        except Exception as e:
            print(f"Exception in get_all {e}")
            raise f"Exception while running get_all query {e}"
            # return {"data": [], "count": 0, "total": 0}
        finally:
            await asyncio.shield(session.close())

    @classmethod
    def convert_to_dict(cls, input_data):
        return {key: value for key, value in input_data.__dict__.items() if not key.startswith("_")}

    @classmethod
    async def delete(cls, row_id, entity_id=None):
        """

        :param row_id:
        :param entity_id:
        :return:
        """
        # entity_id = cls._get_entity_id(entity_id)
        # if not entity_id:
        #     raise "missing context information"
        session = await manager.get_session()
        result = await session.execute(
            select(cls.Config.schema_class).where(cls.Config.schema_class.id == int(row_id))
        )

        if result.scalars().first() is not None:
            status = await session.execute(
                cls.Config.schema_class.__table__.delete().where(cls.Config.schema_class.id == int(row_id))
            )
            
            await session.commit()
            await asyncio.shield(session.close())
            return True, "Success"
        return False, "Fail"

    async def create(self, entity_id=None, upsert=False, upsert_skip_keys = []):
        """

        :param entity_id:
        :param upsert:
        :return:
        """
        # entity_id = self._get_entity_id(entity_id)
        # if not entity_id:
        #     raise "missing context information"
        if not upsert_skip_keys:
            upsert_skip_keys = ["id", "entity_id", "created_at", "updated_at"]
        else:
            upsert_skip_keys = list(set(upsert_skip_keys + ["id", "entity_id", "created_at", "updated_at"]))

        await manager.create_all()
        session = await manager.get_session()
        try:
            if not upsert:
                schema_class = self.Config.schema_class(**{**json.loads(self.model_dump_json()), "entity_id": entity_id})
                session.add(schema_class)
                await session.commit()
                await session.refresh(schema_class)
                return {"id": schema_class.id, **{key: value for key, value in schema_class.__dict__.items() if not key.startswith("_")}}
            else:
                ins_resp = insert(self.Config.schema_class).values([{**json.loads(self.model_dump_json()),
                                                                     "entity_id": entity_id}])
                conflict_dict = {exc.key: exc for exc in ins_resp.excluded if exc.key not in upsert_skip_keys}
                ins_resp = ins_resp.on_conflict_do_update(
                    index_elements=self.Config.upsert_keys, set_=conflict_dict
                )
                resp = await session.execute(ins_resp)
                id = resp.scalar()
                return {"id": id, **{key: value for key, value in resp.__dict__.items() if not key.startswith("_")}}
        except Exception as e:
            print(f"Exception in {'create' if not upsert else 'upsert'} {e}")
            return None
        finally:
            # await session.commit()
            await asyncio.shield(session.close())
        return None

    async def modify(self, entity_id=None):
        """

        :param entity_id:
        :return:
        """
        # entity_id = self._get_entity_id(entity_id)
        # if not entity_id:
        #     raise "missing context information"
        session = await manager.get_session()
        result = await session.execute(
            select(self.Config.schema_class).where(self.Config.schema_class.id == int(self.id))
        )
        record = result.one()
        if len(record):
            for key, value in self.model_dump(exclude_none=True, exclude_unset=True).items():
                setattr(record[0], key, value)
            await session.commit()
            await asyncio.shield(session.close())
            return True, "updated"
        return False, "Record Not Found"
        # record = await session.get(self.Config.schema_class, self.id)
        # print(record)

    @classmethod
    async def bulk_update(cls, records, entity_id=None, upsert=False, upsert_skip_keys = []):
        """

        :param records: list of records to insert as bulk into database
        :param entity_id:
        :param upsert:
        :return:
        """
        # entity_id = cls._get_entity_id(entity_id)
        # if not entity_id:
        #     raise "missing context information"
        if not upsert_skip_keys:
            upsert_skip_keys = ["id", "entity_id", "created_at", "updated_at"]
        else:
            upsert_skip_keys = list(set(upsert_skip_keys + ["id", "entity_id", "created_at", "updated_at"]))

        await manager.create_all()
        session = await manager.get_session()
        try:
            if not upsert:
                tasks = [cls.Config.schema_class(**{**json.loads(json.dumps(rec,
                                                                            default=utils.datetime_serializer)),
                                                    "entity_id": entity_id}) for rec in records]
                session.add_all(tasks)
                await session.commit()  # Commit the transaction
                try:
                    await session.refresh(tasks[0])
                except:
                    ...
                await session.close()
            else:
                # Calculating max records to send for upsert operation by considering max columns limit 32767
                max_limit = int(32767 / (len(records[0]) + 1)) - 1
                for index in range(0, len(records), max_limit):
                    ins_resp = insert(cls.Config.schema_class).values([{**rec, "entity_id": entity_id}
                                                                       for rec in records[index:index+max_limit]])
                    conflict_dict = {exc.key: exc for exc in ins_resp.excluded if exc.key not in upsert_skip_keys}
                    ins_resp = ins_resp.on_conflict_do_update(
                        index_elements=cls.Config.upsert_keys, set_=conflict_dict
                    )
                    await session.execute(ins_resp)
                    await session.commit()  # Commit the transaction
                    try:
                        schema_class = cls.Config.schema_class(**{**records[0],
                                                                  "entity_id": entity_id})
                        await session.refresh(schema_class)
                    except:
                        ...
                    await session.close()
        except Exception as e:
            print(f"Exception in bulk update {e}")
            print(f"Traceback {traceback.format_exc()}")
        finally:
            try:
                await session.commit()  # Commit the transaction
            except:
                ...
            try:
                await asyncio.shield(session.close())
            except:
                ...
        return True, "Data inserted"

    class Config:
        populate_by_name = True
        json_encoders = {
        }
        from_attributes = True
        collection_name: urdhva_base.settings.default_index
        schema_class: Base
        search_fields: []
        upsert_keys: []


# Define concrete model
class PostgresModel(BasePostgresModel):
    id: typing.Optional[int]
    created_at: typing.Optional[datetime.datetime] | None = None
    updated_at: typing.Optional[datetime.datetime] | None = None
    entity_id: typing.Optional[str] | None = None
