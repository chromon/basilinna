# -*- coding: utf-8 -*-

# from database import init_db
# init_db()

# from database import db_session
# from models import User
# u = User('admin', 'admin@localhost')
# db_session.add(u)
# db_session.commit()

# print(User.query.all())

from app import db
from app import models
db.create_all()