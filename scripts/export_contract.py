import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.main import app

if __name__=='__main__':
    Path('docs').mkdir(exist_ok=True)
    Path('docs/openapi.json').write_text(json.dumps(app.openapi(),ensure_ascii=False,indent=2),encoding='utf-8')
    from sqlalchemy.schema import CreateTable,CreateIndex
    from sqlalchemy.dialects import mysql
    from app.models import Base
    dialect=mysql.dialect()
    lines=['-- MySQL 8.4; all timestamps are UTC.','SET NAMES utf8mb4;']
    for t in Base.metadata.sorted_tables:
        lines.append(str(CreateTable(t).compile(dialect=dialect)).strip()+';')
        lines.extend(str(CreateIndex(idx).compile(dialect=dialect))+';' for idx in t.indexes)
    Path('database').mkdir(exist_ok=True)
    Path('database/schema.sql').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    print('Generated docs/openapi.json and database/schema.sql')
