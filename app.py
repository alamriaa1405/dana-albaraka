from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3, os, hashlib
from datetime import datetime, date, timedelta
from urllib.parse import quote

app=Flask(__name__); app.secret_key=os.environ.get('SECRET_KEY','dana-local-secret')
DATA_DIR=os.environ.get('DATA_DIR', os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB=os.path.join(DATA_DIR,'dana.db')
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def h(x): return hashlib.sha256(x.encode()).hexdigest()
def init_db():
 c=db(); c.executescript('''
 CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,category TEXT,unit TEXT DEFAULT 'حبة',barcode_piece TEXT UNIQUE,barcode_pack TEXT,pack_qty INTEGER DEFAULT 1,barcode_carton TEXT,carton_qty INTEGER DEFAULT 1,cost REAL DEFAULT 0,sale_price REAL DEFAULT 0,stock REAL DEFAULT 0,min_stock REAL DEFAULT 0,expiry TEXT,last_sale TEXT);
 CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT,balance REAL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT,balance REAL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,customer_id INTEGER,total REAL NOT NULL,payment_method TEXT DEFAULT 'نقدي',locked INTEGER DEFAULT 1,status TEXT DEFAULT 'مكتملة');
 CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER NOT NULL,product_id INTEGER NOT NULL,qty REAL NOT NULL,price REAL NOT NULL,subtotal REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,supplier_id INTEGER,product_id INTEGER NOT NULL,qty REAL NOT NULL,unit_cost REAL NOT NULL,total REAL NOT NULL,attachment TEXT);
 CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,title TEXT NOT NULL,amount REAL NOT NULL,note TEXT);
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT DEFAULT 'موظف',permissions TEXT DEFAULT 'بيع',active INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,user TEXT,action TEXT,details TEXT);
 ''')
 # migrations
 for sql in ["ALTER TABLE sales ADD COLUMN status TEXT DEFAULT 'مكتملة'", "ALTER TABLE users ADD COLUMN password_hash TEXT"]:
  try:c.execute(sql)
  except:pass
 if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone(): c.execute('INSERT INTO users(username,password_hash,role,permissions) VALUES(?,?,?,?)',('admin',h('admin123'),'مشرف','الكل'))
 else:
  c.execute("UPDATE users SET password_hash=? WHERE password_hash IS NULL OR password_hash=''",(h('admin123'),))
 c.commit(); c.close()
def audit(action,details=''):
 c=db(); c.execute('INSERT INTO audit(created_at,user,action,details) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),session.get('user','system'),action,details)); c.commit(); c.close()
def allowed(p): return session.get('role')=='مشرف' or p in (session.get('permissions') or '').split(',') or session.get('permissions')=='الكل'
@app.before_request
def auth():
 if request.endpoint in ('login','static'): return
 if 'user' not in session: return redirect(url_for('login'))
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  c=db(); u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(request.form['username'],)).fetchone(); c.close()
  if u and u['password_hash']==h(request.form['password']): session.update(user=u['username'],role=u['role'],permissions=u['permissions']); return redirect('/')
  flash('بيانات الدخول غير صحيحة')
 return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect('/login')
@app.route('/')
def dashboard():
 c=db(); today=date.today().isoformat(); soon=(date.today()+timedelta(days=30)).isoformat(); stale=(date.today()-timedelta(days=60)).isoformat()
 vals=dict(sales_today=c.execute("SELECT COALESCE(SUM(total),0)x FROM sales WHERE substr(created_at,1,10)=? AND status='مكتملة'",(today,)).fetchone()['x'], expenses_today=c.execute("SELECT COALESCE(SUM(amount),0)x FROM expenses WHERE substr(created_at,1,10)=?",(today,)).fetchone()['x'], stock_value=c.execute('SELECT COALESCE(SUM(stock*cost),0)x FROM products').fetchone()['x'], low=c.execute('SELECT COUNT(*)x FROM products WHERE stock<=min_stock').fetchone()['x'], exp=c.execute("SELECT COUNT(*)x FROM products WHERE expiry IS NOT NULL AND expiry<>'' AND expiry<=?",(soon,)).fetchone()['x'], stale=c.execute('SELECT COUNT(*)x FROM products WHERE stock>0 AND (last_sale IS NULL OR last_sale<?)',(stale,)).fetchone()['x'], recent=c.execute('SELECT * FROM sales ORDER BY id DESC LIMIT 8').fetchall()); c.close(); return render_template('dashboard.html',**vals)
@app.route('/products',methods=['GET','POST'])
def products():
 if not allowed('مخزون'): flash('لا توجد صلاحية'); return redirect('/')
 c=db()
 if request.method=='POST':
  f=request.form
  try:c.execute('INSERT INTO products(name,category,barcode_piece,barcode_pack,pack_qty,barcode_carton,carton_qty,cost,sale_price,stock,min_stock,expiry) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(f['name'],f.get('category'),f.get('barcode_piece') or None,f.get('barcode_pack') or None,int(f.get('pack_qty') or 1),f.get('barcode_carton') or None,int(f.get('carton_qty') or 1),float(f.get('cost') or 0),float(f.get('sale_price') or 0),float(f.get('stock') or 0),float(f.get('min_stock') or 0),f.get('expiry') or None)); c.commit(); audit('إضافة منتج',f['name']); flash('تمت إضافة المنتج')
  except Exception as e: flash('تعذر الحفظ: '+str(e))
  c.close(); return redirect('/products')
 rows=c.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); c.close(); return render_template('products.html',rows=rows)
@app.route('/purchase',methods=['GET','POST'])
def purchase():
 if not allowed('مشتريات'): flash('لا توجد صلاحية'); return redirect('/')
 c=db()
 if request.method=='POST':
  f=request.form; pid=int(f['product_id']); qty=float(f['qty']); cost=float(f['unit_cost']); p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone(); warning=cost>float(p['cost'] or 0)>0
  c.execute('INSERT INTO purchases(created_at,supplier_id,product_id,qty,unit_cost,total,attachment) VALUES(?,?,?,?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),f.get('supplier_id') or None,pid,qty,cost,qty*cost,f.get('attachment') or None)); c.execute('UPDATE products SET stock=stock+?,cost=? WHERE id=?',(qty,cost,pid)); c.commit(); audit('مشتريات',p['name']); flash(('تنبيه: سعر الشراء أعلى من التكلفة السابقة. ' if warning else '')+'تم تسجيل المشتريات'); c.close(); return redirect('/purchase')
 ps=c.execute('SELECT * FROM products ORDER BY name').fetchall(); ss=c.execute('SELECT * FROM suppliers ORDER BY name').fetchall(); c.close(); return render_template('purchase.html',products=ps,suppliers=ss)
@app.route('/pos',methods=['GET','POST'])
def pos():
 if not allowed('بيع'): flash('لا توجد صلاحية'); return redirect('/')
 c=db(); customers=c.execute('SELECT * FROM customers ORDER BY name').fetchall()
 if request.method=='POST':
  b=request.form['barcode'].strip(); q=float(request.form.get('qty') or 1); p=c.execute('SELECT *,CASE WHEN barcode_piece=? THEN 1 WHEN barcode_pack=? THEN pack_qty WHEN barcode_carton=? THEN carton_qty ELSE 0 END mult FROM products WHERE barcode_piece=? OR barcode_pack=? OR barcode_carton=? LIMIT 1',(b,b,b,b,b,b)).fetchone()
  if not p: c.close(); flash('الباركود غير موجود'); return redirect('/pos')
  rq=q*float(p['mult']); total=rq*float(p['sale_price']); cid=request.form.get('customer_id') or None; pay=request.form.get('payment_method') or 'نقدي'
  if p['stock']<rq: c.close(); flash('الكمية غير كافية'); return redirect('/pos')
  cur=c.execute('INSERT INTO sales(created_at,customer_id,total,payment_method,locked,status) VALUES(?,?,?,?,1,?)',(datetime.now().isoformat(timespec='seconds'),cid,total,pay,'مكتملة')); sid=cur.lastrowid; c.execute('INSERT INTO sale_items(sale_id,product_id,qty,price,subtotal) VALUES(?,?,?,?,?)',(sid,p['id'],rq,p['sale_price'],total)); c.execute('UPDATE products SET stock=stock-?,last_sale=? WHERE id=?',(rq,date.today().isoformat(),p['id']));
  if pay=='آجل' and cid: c.execute('UPDATE customers SET balance=balance+? WHERE id=?',(total,cid))
  c.commit(); audit('بيع',f'فاتورة {sid}'); c.close(); return redirect(f'/invoice/{sid}')
 c.close(); return render_template('pos.html',customers=customers)
@app.route('/invoice/<int:sale_id>')
def invoice(sale_id):
 c=db(); sale=c.execute('SELECT s.*,c.name customer_name,c.phone customer_phone FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?',(sale_id,)).fetchone(); items=c.execute('SELECT si.*,p.name FROM sale_items si JOIN products p ON p.id=si.product_id WHERE sale_id=?',(sale_id,)).fetchall(); c.close(); return render_template('invoice.html',sale=sale,items=items)
@app.route('/return/<int:sale_id>',methods=['POST'])
def sale_return(sale_id):
 if session.get('role')!='مشرف': flash('المرتجع للمشرف فقط'); return redirect(f'/invoice/{sale_id}')
 c=db(); s=c.execute('SELECT * FROM sales WHERE id=?',(sale_id,)).fetchone()
 if not s or s['status']=='مرتجع': c.close(); flash('الفاتورة مرتجعة مسبقاً'); return redirect(f'/invoice/{sale_id}')
 for i in c.execute('SELECT * FROM sale_items WHERE sale_id=?',(sale_id,)).fetchall(): c.execute('UPDATE products SET stock=stock+? WHERE id=?',(i['qty'],i['product_id']))
 if s['payment_method']=='آجل' and s['customer_id']: c.execute('UPDATE customers SET balance=MAX(0,balance-?) WHERE id=?',(s['total'],s['customer_id']))
 c.execute("UPDATE sales SET status='مرتجع' WHERE id=?",(sale_id,)); c.commit(); audit('مرتجع',f'فاتورة {sale_id}'); c.close(); flash('تم تسجيل المرتجع بقيد عكسي دون حذف الفاتورة الأصلية'); return redirect(f'/invoice/{sale_id}')
@app.route('/contacts',methods=['GET','POST'])
def contacts():
 c=db()
 if request.method=='POST':
  t='customers' if request.form['type']=='customer' else 'suppliers'; c.execute(f'INSERT INTO {t}(name,phone) VALUES(?,?)',(request.form['name'],request.form.get('phone'))); c.commit(); flash('تمت الإضافة'); return redirect('/contacts')
 cs=c.execute('SELECT * FROM customers ORDER BY id DESC').fetchall(); ss=c.execute('SELECT * FROM suppliers ORDER BY id DESC').fetchall(); c.close(); return render_template('contacts.html',customers=cs,suppliers=ss)
@app.route('/expenses',methods=['GET','POST'])
def expenses():
 c=db()
 if request.method=='POST': c.execute('INSERT INTO expenses(created_at,title,amount,note) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),request.form['title'],float(request.form['amount']),request.form.get('note'))); c.commit(); audit('مصروف',request.form['title']); return redirect('/expenses')
 rows=c.execute('SELECT * FROM expenses ORDER BY id DESC LIMIT 100').fetchall(); c.close(); return render_template('expenses.html',rows=rows)
@app.route('/users',methods=['GET','POST'])
def users():
 if session.get('role')!='مشرف': flash('للمشرف فقط'); return redirect('/')
 c=db()
 if request.method=='POST': c.execute('INSERT INTO users(username,password_hash,role,permissions) VALUES(?,?,?,?)',(request.form['username'],h(request.form['password']),request.form['role'],','.join(request.form.getlist('permissions')))); c.commit(); audit('إضافة مستخدم',request.form['username']); return redirect('/users')
 rows=c.execute('SELECT id,username,role,permissions,active FROM users').fetchall(); logs=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 50').fetchall(); c.close(); return render_template('users.html',rows=rows,logs=logs)
@app.route('/reports')
def reports():
 c=db(); sales=c.execute("SELECT substr(created_at,1,10)d,SUM(CASE WHEN status='مكتملة' THEN total ELSE 0 END) total,COUNT(*)n FROM sales GROUP BY d ORDER BY d DESC LIMIT 30").fetchall(); c.close(); return render_template('reports.html',sales=sales)
init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
