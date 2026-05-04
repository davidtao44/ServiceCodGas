from app.core.database.database import engine
from sqlalchemy import text

# Test if we can query transportador1
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, email, role FROM users WHERE email = 'transportador1@codgas.com'"))
    row = result.first()
    if row:
        print('User found: ID=' + str(row[0]) + ', Email=' + row[1] + ', Role=' + str(row[2]))
    else:
        print('User not found')
