
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3, os, hashlib
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dana-rowaa-v2-secret")
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, "dana.db")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def h(x): return hashlib.sha256(x.encode()).hexdigest()
def now(): return datetime.now().isoformat(timespec="seconds")

def ensure_column(c, table, coldef):
    col = coldef.split()[0]
    cols = [r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      sku TEXT,
      category TEXT,
      brand TEXT,
      supplier_id INTEGER,
      unit TEXT DEFAULT 'حبة',
      barcode_piece TEXT UNIQUE,
      barcode_pack TEXT,
      pack_qty INTEGER DEFAULT 1,
      barcode_carton TEXT,
      carton_qty INTEGER DEFAULT 1,
      cost REAL DEFAULT 0,
      sale_price REAL DEFAULT 0,
      wholesale_price REAL DEFAULT 0,
      stock REAL DEFAULT 0,
      min_stock REAL DEFAULT 0,
      expiry TEXT,
      last_sale TEXT,
      track_stock INTEGER DEFAULT 1,
      weighted INTEGER DEFAULT 0,
      sellable INTEGER DEFAULT 1,
      purchasable INTEGER DEFAULT 1,
      description TEXT
    );

    CREATE TABLE IF NOT EXISTS product_packs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      pack_size REAL NOT NULL DEFAULT 1,
      sku TEXT UNIQUE NOT NULL,
      sale_price REAL DEFAULT 0,
      wholesale_price REAL DEFAULT 0,
      cost REAL DEFAULT 0,
      sellable INTEGER DEFAULT 1,
      purchasable INTEGER DEFAULT 1,
      FOREIGN KEY(product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS categories(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS customers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      phone TEXT,
      email TEXT,
      balance REAL DEFAULT 0,
      credit_limit REAL DEFAULT 0,
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS suppliers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      phone TEXT,
      email TEXT,
      city TEXT,
      balance REAL DEFAULT 0,
      credit_limit REAL DEFAULT 0,
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS sales(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      customer_id INTEGER,
      total REAL NOT NULL,
      payment_method TEXT DEFAULT 'نقدي',
      locked INTEGER DEFAULT 1,
      status TEXT DEFAULT 'مكتملة',
      location TEXT DEFAULT 'الفرع الرئيسي',
      employee TEXT,
      paid REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS sale_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sale_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      qty REAL NOT NULL,
      price REAL NOT NULL,
      subtotal REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS customer_payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      customer_id INTEGER NOT NULL,
      amount REAL NOT NULL,
      method TEXT,
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS purchases(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      supplier_id INTEGER,
      invoice_no TEXT,
      status TEXT DEFAULT 'معتمدة',
      payment_status TEXT DEFAULT 'مدفوع',
      payment_method TEXT DEFAULT 'نقدي',
      attachment TEXT,
      total REAL DEFAULT 0,
      location TEXT DEFAULT 'الفرع الرئيسي'
    );
    CREATE TABLE IF NOT EXISTS purchase_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      purchase_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      qty REAL NOT NULL,
      unit_cost REAL NOT NULL,
      subtotal REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS purchase_returns(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      supplier_id INTEGER,
      purchase_id INTEGER,
      total REAL DEFAULT 0,
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS supplier_payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      supplier_id INTEGER NOT NULL,
      amount REAL NOT NULL,
      method TEXT,
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS expenses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      title TEXT NOT NULL,
      category TEXT,
      location TEXT DEFAULT 'الفرع الرئيسي',
      amount REAL NOT NULL,
      status TEXT DEFAULT 'مدفوع',
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS fixed_assets(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      purchase_date TEXT,
      cost REAL DEFAULT 0,
      useful_life INTEGER DEFAULT 0,
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS journal_entries(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      ref TEXT,
      entry_type TEXT,
      debit REAL DEFAULT 0,
      credit REAL DEFAULT 0,
      note TEXT,
      location TEXT DEFAULT 'الفرع الرئيسي'
    );
    CREATE TABLE IF NOT EXISTS accounts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT,
      name TEXT NOT NULL,
      parent_id INTEGER,
      account_type TEXT,
      nature TEXT,
      balance REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS stock_docs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      doc_type TEXT,
      product_id INTEGER,
      qty REAL,
      note TEXT,
      location TEXT DEFAULT 'الفرع الرئيسي'
    );
    CREATE TABLE IF NOT EXISTS stock_counts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      location TEXT,
      status TEXT DEFAULT 'مسودة',
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS stock_transfers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      from_location TEXT,
      to_location TEXT,
      product_id INTEGER,
      qty REAL,
      status TEXT DEFAULT 'مكتمل'
    );
    CREATE TABLE IF NOT EXISTS cashboxes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      location TEXT DEFAULT 'الفرع الرئيسي',
      user TEXT,
      status TEXT DEFAULT 'نشط'
    );
    CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY,
      value TEXT
    );
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT DEFAULT 'موظف',
      permissions TEXT DEFAULT 'بيع',
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT,
      user TEXT,
      action TEXT,
      details TEXT
    );
    """)
    # migration for earlier DBs
    for table, defs in {
        "products":[
            "sku TEXT","brand TEXT","supplier_id INTEGER","wholesale_price REAL DEFAULT 0",
            "track_stock INTEGER DEFAULT 1","weighted INTEGER DEFAULT 0","sellable INTEGER DEFAULT 1",
            "purchasable INTEGER DEFAULT 1","description TEXT"
        ],
        "customers":["email TEXT","credit_limit REAL DEFAULT 0","active INTEGER DEFAULT 1"],
        "suppliers":["email TEXT","city TEXT","credit_limit REAL DEFAULT 0","active INTEGER DEFAULT 1"],
        "sales":["location TEXT DEFAULT 'الفرع الرئيسي'","employee TEXT","paid REAL DEFAULT 0"],
        "expenses":["category TEXT","location TEXT DEFAULT 'الفرع الرئيسي'","status TEXT DEFAULT 'مدفوع'"],
    }.items():
        for d in defs:
            ensure_column(c, table, d)
    if not c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        c.execute("INSERT INTO users(username,password_hash,role,permissions) VALUES(?,?,?,?)",
                  ("admin",h("admin123"),"مشرف","الكل"))
    if not c.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
        roots = [
            ("1000","الأصول","أصول","مدين"),("2000","الالتزامات","التزامات","دائن"),
            ("3000","حقوق الملكية","حقوق الملكية","دائن"),("4000","الإيرادات","إيرادات","دائن"),
            ("5000","المصروفات","مصروفات","مدين")
        ]
        c.executemany("INSERT INTO accounts(code,name,account_type,nature) VALUES(?,?,?,?)", roots)
    if not c.execute("SELECT 1 FROM cashboxes LIMIT 1").fetchone():
        c.execute("INSERT INTO cashboxes(name,location,user,status) VALUES(?,?,?,?)",
                  ("الصندوق الرئيسي","الفرع الرئيسي","admin","نشط"))
    c.commit(); c.close()

def audit(action, details=""):
    c=db()
    c.execute("INSERT INTO audit(created_at,user,action,details) VALUES(?,?,?,?)",
              (now(),session.get("user","system"),action,details))
    c.commit(); c.close()

def allowed(p):
    return session.get("role")=="مشرف" or session.get("permissions")=="الكل" or p in (session.get("permissions") or "").split(",")

def generate_sku(c):
    # رقم رقمي مناسب للإدخال اليدوي أو القراءة بقارئ الباركود.
    # يستمر بالتوليد حتى يجد رقماً غير مستخدم لا في المنتجات ولا الحزم.
    import random
    while True:
        code = str(random.randint(100000000000, 999999999999))
        exists = c.execute("SELECT 1 FROM products WHERE sku=? LIMIT 1",(code,)).fetchone()
        if not exists:
            exists = c.execute("SELECT 1 FROM product_packs WHERE sku=? LIMIT 1",(code,)).fetchone()
        if not exists:
            return code

def find_product(c, code):
    code=(code or "").strip()
    if not code: return None

    p = c.execute("SELECT * FROM products WHERE sku=? OR CAST(id AS TEXT)=? LIMIT 1",(code,code)).fetchone()
    if p:
        d=dict(p)
        d["mult"]=1
        d["lookup_sku"]=p["sku"]
        d["pack_name"]=None
        return d

    pk = c.execute("""
      SELECT pk.*, p.name product_name, p.stock, p.track_stock,
             p.cost base_cost, p.sale_price base_sale_price,
             p.wholesale_price base_wholesale_price, p.id base_product_id
      FROM product_packs pk
      JOIN products p ON p.id=pk.product_id
      WHERE pk.sku=?
      LIMIT 1
    """,(code,)).fetchone()
    if pk:
        # نحول سعر الحزمة إلى سعر لكل وحدة داخل الحزمة حتى تبقى
        # معادلات المخزون القديمة صحيحة مع احتساب pack_size كمضاعف.
        size=float(pk["pack_size"] or 1)
        return {
            "id": pk["base_product_id"],
            "name": pk["product_name"] + " - " + pk["name"],
            "stock": pk["stock"],
            "track_stock": pk["track_stock"],
            "cost": (float(pk["cost"] or 0)/size) if float(pk["cost"] or 0)>0 else pk["base_cost"],
            "sale_price": (float(pk["sale_price"] or 0)/size) if float(pk["sale_price"] or 0)>0 else pk["base_sale_price"],
            "wholesale_price": (float(pk["wholesale_price"] or 0)/size) if float(pk["wholesale_price"] or 0)>0 else pk["base_wholesale_price"],
            "mult": size,
            "lookup_sku": pk["sku"],
            "pack_name": pk["name"],
        }
    return None

@app.before_request
def auth():
    if request.endpoint in ("login","static"): return
    if "user" not in session: return redirect(url_for("login"))

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        c=db(); u=c.execute("SELECT * FROM users WHERE username=? AND active=1",(request.form["username"],)).fetchone(); c.close()
        if u and u["password_hash"]==h(request.form["password"]):
            session.update(user=u["username"],role=u["role"],permissions=u["permissions"]); return redirect("/")
        flash("بيانات الدخول غير صحيحة")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect("/login")

@app.route("/")
def dashboard():
    c=db(); today=date.today().isoformat()
    sales_today=c.execute("SELECT COALESCE(SUM(total),0)x FROM sales WHERE substr(created_at,1,10)=? AND status='مكتملة'",(today,)).fetchone()["x"]
    sale_count=c.execute("SELECT COUNT(*)x FROM sales WHERE substr(created_at,1,10)=? AND status='مكتملة'",(today,)).fetchone()["x"]
    cost_today=c.execute("""SELECT COALESCE(SUM(si.qty*p.cost),0)x FROM sale_items si JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id WHERE substr(s.created_at,1,10)=? AND s.status='مكتملة'""",(today,)).fetchone()["x"]
    gross=sales_today-cost_today
    exp_today=c.execute("SELECT COALESCE(SUM(amount),0)x FROM expenses WHERE substr(created_at,1,10)=?",(today,)).fetchone()["x"]
    net=gross-exp_today
    stock_value=c.execute("SELECT COALESCE(SUM(stock*cost),0)x FROM products").fetchone()["x"]
    collected=c.execute("SELECT COALESCE(SUM(paid),0)x FROM sales WHERE substr(created_at,1,10)=?",(today,)).fetchone()["x"]
    days=c.execute("""SELECT substr(created_at,1,10)d, SUM(CASE WHEN status='مكتملة' THEN total ELSE 0 END) total
                      FROM sales WHERE created_at>=datetime('now','-14 day') GROUP BY d ORDER BY d""").fetchall()
    recent=c.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 8").fetchall()
    c.close()
    return render_template("dashboard.html",sales_today=sales_today,sale_count=sale_count,gross=gross,net=net,
                           stock_value=stock_value,collected=collected,recent=recent,
                           chart_labels=[x["d"] for x in days],chart_values=[x["total"] for x in days])


@app.route("/api/generate-sku")
def api_generate_sku():
    c=db()
    code=generate_sku(c)
    c.close()
    return jsonify({"ok":True,"sku":code})

@app.route("/api/product-by-code")
def api_product():
    c=db(); p=find_product(c,request.args.get("code")); c.close()
    if not p: return jsonify({"ok":False}),404
    return jsonify({"ok":True,"id":p["id"],"name":p["name"],"stock":p["stock"],"cost":p["cost"],"sale_price":p["sale_price"],"mult":p["mult"]})

# ---------- SALES ----------
@app.route("/pos",methods=["GET","POST"])
def pos():
    if not allowed("بيع"): flash("لا توجد صلاحية"); return redirect("/")
    c=db(); customers=c.execute("SELECT * FROM customers WHERE active=1 ORDER BY name").fetchall()
    if request.method=="POST":
        p=find_product(c,request.form["barcode"]); q=float(request.form.get("qty") or 1)
        if not p: c.close(); flash("الكود أو الباركود غير موجود"); return redirect("/pos")
        rq=q*float(p["mult"] or 1)
        if p["track_stock"] and float(p["stock"] or 0)<rq: c.close(); flash("الكمية غير كافية"); return redirect("/pos")
        total=rq*float(p["sale_price"] or 0); cid=request.form.get("customer_id") or None; method=request.form.get("payment_method") or "نقدي"
        paid=total if method!="آجل" else 0
        cur=c.execute("""INSERT INTO sales(created_at,customer_id,total,payment_method,status,location,employee,paid)
                         VALUES(?,?,?,?,?,?,?,?)""",(now(),cid,total,method,"مكتملة","الفرع الرئيسي",session.get("user"),paid))
        sid=cur.lastrowid
        c.execute("INSERT INTO sale_items(sale_id,product_id,qty,price,subtotal) VALUES(?,?,?,?,?)",(sid,p["id"],rq,p["sale_price"],total))
        if p["track_stock"]: c.execute("UPDATE products SET stock=stock-?,last_sale=? WHERE id=?",(rq,date.today().isoformat(),p["id"]))
        if method=="آجل" and cid: c.execute("UPDATE customers SET balance=balance+? WHERE id=?",(total,cid))
        c.commit(); c.close(); audit("بيع",f"فاتورة {sid}"); return redirect(f"/invoice/{sid}")
    c.close(); return render_template("pos.html",customers=customers)

@app.route("/sales/invoices")
def sales_invoices():
    q=(request.args.get("q") or "").strip(); c=db()
    sql="""SELECT s.*,c.name customer_name FROM sales s LEFT JOIN customers c ON c.id=s.customer_id"""
    params=[]
    if q:
        sql+=" WHERE CAST(s.id AS TEXT) LIKE ? OR c.name LIKE ?"; params=[f"%{q}%",f"%{q}%"]
    sql+=" ORDER BY s.id DESC LIMIT 200"
    rows=c.execute(sql,params).fetchall(); c.close()
    return render_template("sales_invoices.html",rows=rows,q=q)

@app.route("/sales/cashboxes")
def cashboxes():
    c=db(); rows=c.execute("SELECT * FROM cashboxes ORDER BY id DESC").fetchall(); c.close()
    return render_template("cashboxes.html",rows=rows)

@app.route("/sales/digital-menu")
def digital_menu(): return render_template("simple_page.html",title="المنيو الرقمي",subtitle="إدارة قوائم العرض الرقمية",items=["إنشاء قائمة رقمية","ربط المنتجات","تخصيص العرض"])

@app.route("/sales/promotions")
def promotions(): return render_template("simple_page.html",title="العروض الترويجية",subtitle="إدارة الخصومات والعروض",items=["خصم نسبة","خصم مبلغ","عروض على منتجات محددة"])

@app.route("/sales/ecommerce")
def ecommerce(): return render_template("simple_page.html",title="طلبات المتجر الإلكتروني",subtitle="إدارة الطلبات الواردة من المتجر الإلكتروني",items=["طلبات جديدة","قيد التجهيز","مكتملة"])

@app.route("/sales/settings",methods=["GET","POST"])
def sales_settings():
    keys=["allow_sale","show_price","allow_below_cost","simple_tax_invoice","track_stock","allow_notes"]
    c=db()
    if request.method=="POST":
        for k in keys:
            v="1" if request.form.get(k) else "0"
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v))
        c.commit(); flash("تم حفظ إعدادات البيع")
    vals={k:(c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone() or {"value":"1"})["value"] for k in keys}
    c.close(); return render_template("sales_settings.html",vals=vals)

@app.route("/invoice/<int:sale_id>")
def invoice(sale_id):
    c=db()
    sale=c.execute("""SELECT s.*,c.name customer_name,c.phone customer_phone FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?""",(sale_id,)).fetchone()
    items=c.execute("""SELECT si.*,p.name FROM sale_items si JOIN products p ON p.id=si.product_id WHERE sale_id=?""",(sale_id,)).fetchall()
    c.close(); return render_template("invoice.html",sale=sale,items=items)

@app.route("/return/<int:sale_id>",methods=["POST"])
def sale_return(sale_id):
    if session.get("role")!="مشرف": flash("المرتجع للمشرف فقط"); return redirect(f"/invoice/{sale_id}")
    c=db(); s=c.execute("SELECT * FROM sales WHERE id=?",(sale_id,)).fetchone()
    if not s or s["status"]=="مرتجع": c.close(); flash("الفاتورة مرتجعة مسبقاً"); return redirect(f"/invoice/{sale_id}")
    for i in c.execute("SELECT * FROM sale_items WHERE sale_id=?",(sale_id,)).fetchall():
        c.execute("UPDATE products SET stock=stock+? WHERE id=?",(i["qty"],i["product_id"]))
    if s["payment_method"]=="آجل" and s["customer_id"]:
        c.execute("UPDATE customers SET balance=MAX(0,balance-?) WHERE id=?",(s["total"],s["customer_id"]))
    c.execute("UPDATE sales SET status='مرتجع' WHERE id=?",(sale_id,)); c.commit(); c.close(); audit("مرتجع",f"فاتورة {sale_id}")
    flash("تم تسجيل المرتجع"); return redirect(f"/invoice/{sale_id}")

# ---------- CUSTOMERS ----------
@app.route("/customers",methods=["GET","POST"])
def customers():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO customers(name,phone,email,credit_limit) VALUES(?,?,?,?)",
                  (request.form["name"],request.form.get("phone"),request.form.get("email"),float(request.form.get("credit_limit") or 0)))
        c.commit(); flash("تمت إضافة العميل")
    q=(request.args.get("q") or "").strip()
    if q:
        rows=c.execute("SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? ORDER BY id DESC",(f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    else: rows=c.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    c.close(); return render_template("customers.html",rows=rows,q=q)

@app.route("/customer-payments",methods=["GET","POST"])
def customer_payments():
    c=db(); cs=c.execute("SELECT * FROM customers ORDER BY name").fetchall()
    if request.method=="POST":
        cid=int(request.form["customer_id"]); amt=float(request.form["amount"]); method=request.form.get("method") or "نقدي"
        c.execute("INSERT INTO customer_payments(created_at,customer_id,amount,method,note) VALUES(?,?,?,?,?)",(now(),cid,amt,method,request.form.get("note")))
        c.execute("UPDATE customers SET balance=MAX(0,balance-?) WHERE id=?",(amt,cid)); c.commit(); flash("تم تسجيل دفعة العميل")
    rows=c.execute("""SELECT cp.*,c.name customer_name FROM customer_payments cp JOIN customers c ON c.id=cp.customer_id ORDER BY cp.id DESC LIMIT 200""").fetchall()
    c.close(); return render_template("customer_payments.html",rows=rows,customers=cs)

# ---------- PRODUCTS / INVENTORY ----------
@app.route("/products",methods=["GET"])
def products():
    if not allowed("مخزون"): flash("لا توجد صلاحية"); return redirect("/")
    q=(request.args.get("q") or "").strip(); c=db()
    if q:
        rows=c.execute("""SELECT * FROM products WHERE name LIKE ? OR sku LIKE ? OR barcode_piece LIKE ? OR CAST(id AS TEXT)=? ORDER BY id DESC""",
                       (f"%{q}%",f"%{q}%",f"%{q}%",q)).fetchall()
    else: rows=c.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    c.close(); return render_template("products.html",rows=rows,q=q)

@app.route("/products/new",methods=["GET","POST"])
def product_new():
    if not allowed("مخزون"): flash("لا توجد صلاحية"); return redirect("/")
    c=db(); cats=c.execute("SELECT * FROM categories ORDER BY name").fetchall(); sups=c.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    if request.method=="POST":
        f=request.form
        sku=(f.get("sku") or "").strip() or generate_sku(c)
        try:
            cur=c.execute("""INSERT INTO products(name,sku,category,brand,supplier_id,unit,
                       cost,sale_price,wholesale_price,stock,min_stock,expiry,track_stock,weighted,sellable,purchasable,description)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (f["name"],sku,f.get("category"),f.get("brand"),f.get("supplier_id") or None,f.get("unit") or "حبة",
                       float(f.get("cost") or 0),float(f.get("sale_price") or 0),float(f.get("wholesale_price") or 0),
                       float(f.get("stock") or 0),float(f.get("min_stock") or 0),f.get("expiry") or None,
                       1 if f.get("track_stock") else 0,1 if f.get("weighted") else 0,
                       1 if f.get("sellable") else 0,1 if f.get("purchasable") else 0,f.get("description")))
            pid=cur.lastrowid

            pack_names=request.form.getlist("pack_name[]")
            pack_sizes=request.form.getlist("pack_size[]")
            pack_skus=request.form.getlist("pack_sku[]")
            pack_sale_prices=request.form.getlist("pack_sale_price[]")
            pack_wholesale_prices=request.form.getlist("pack_wholesale_price[]")
            pack_costs=request.form.getlist("pack_cost[]")
            for i, name in enumerate(pack_names):
                name=(name or "").strip()
                if not name: continue
                psku=(pack_skus[i] if i < len(pack_skus) else "").strip() or generate_sku(c)
                psize=float(pack_sizes[i] if i < len(pack_sizes) and pack_sizes[i] else 1)
                psale=float(pack_sale_prices[i] if i < len(pack_sale_prices) and pack_sale_prices[i] else 0)
                pwhole=float(pack_wholesale_prices[i] if i < len(pack_wholesale_prices) and pack_wholesale_prices[i] else 0)
                pcost=float(pack_costs[i] if i < len(pack_costs) and pack_costs[i] else 0)
                c.execute("""INSERT INTO product_packs(product_id,name,pack_size,sku,sale_price,wholesale_price,cost,sellable,purchasable)
                             VALUES(?,?,?,?,?,?,?,?,?)""",
                          (pid,name,psize,psku,psale,pwhole,pcost,1,1))
            c.commit(); audit("إضافة منتج",f["name"]); flash("تمت إضافة المنتج"); c.close(); return redirect("/products")
        except Exception as e:
            c.rollback()
            flash("تعذر الحفظ: "+str(e))
    c.close(); return render_template("product_form.html",p=None,packs=[],categories=cats,suppliers=sups)

@app.route("/products/edit/<int:pid>",methods=["GET","POST"])
def product_edit(pid):
    c=db(); p=c.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    packs=c.execute("SELECT * FROM product_packs WHERE product_id=? ORDER BY id",(pid,)).fetchall()
    cats=c.execute("SELECT * FROM categories ORDER BY name").fetchall(); sups=c.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    if not p: c.close(); flash("المنتج غير موجود"); return redirect("/products")
    if request.method=="POST":
        f=request.form
        sku=(f.get("sku") or "").strip() or p["sku"] or generate_sku(c)
        try:
            c.execute("""UPDATE products SET name=?,sku=?,category=?,brand=?,supplier_id=?,unit=?,
                         cost=?,sale_price=?,wholesale_price=?,stock=?,min_stock=?,expiry=?,track_stock=?,weighted=?,sellable=?,purchasable=?,description=? WHERE id=?""",
                      (f["name"],sku,f.get("category"),f.get("brand"),f.get("supplier_id") or None,f.get("unit") or "حبة",
                       float(f.get("cost") or 0),float(f.get("sale_price") or 0),float(f.get("wholesale_price") or 0),
                       float(f.get("stock") or 0),float(f.get("min_stock") or 0),f.get("expiry") or None,
                       1 if f.get("track_stock") else 0,1 if f.get("weighted") else 0,
                       1 if f.get("sellable") else 0,1 if f.get("purchasable") else 0,f.get("description"),pid))
            c.execute("DELETE FROM product_packs WHERE product_id=?",(pid,))
            pack_names=request.form.getlist("pack_name[]")
            pack_sizes=request.form.getlist("pack_size[]")
            pack_skus=request.form.getlist("pack_sku[]")
            pack_sale_prices=request.form.getlist("pack_sale_price[]")
            pack_wholesale_prices=request.form.getlist("pack_wholesale_price[]")
            pack_costs=request.form.getlist("pack_cost[]")
            for i, name in enumerate(pack_names):
                name=(name or "").strip()
                if not name: continue
                psku=(pack_skus[i] if i < len(pack_skus) else "").strip() or generate_sku(c)
                psize=float(pack_sizes[i] if i < len(pack_sizes) and pack_sizes[i] else 1)
                psale=float(pack_sale_prices[i] if i < len(pack_sale_prices) and pack_sale_prices[i] else 0)
                pwhole=float(pack_wholesale_prices[i] if i < len(pack_wholesale_prices) and pack_wholesale_prices[i] else 0)
                pcost=float(pack_costs[i] if i < len(pack_costs) and pack_costs[i] else 0)
                c.execute("""INSERT INTO product_packs(product_id,name,pack_size,sku,sale_price,wholesale_price,cost,sellable,purchasable)
                             VALUES(?,?,?,?,?,?,?,?,?)""",(pid,name,psize,psku,psale,pwhole,pcost,1,1))
            c.commit(); c.close(); flash("تم تحديث المنتج"); return redirect("/products")
        except Exception as e:
            c.rollback(); flash("تعذر الحفظ: "+str(e))
    c.close(); return render_template("product_form.html",p=p,packs=packs,categories=cats,suppliers=sups)

@app.route("/categories",methods=["GET","POST"])
def categories():
    c=db()
    if request.method=="POST":
        try:c.execute("INSERT INTO categories(name) VALUES(?)",(request.form["name"],)); c.commit()
        except: flash("التصنيف موجود مسبقًا")
    rows=c.execute("SELECT * FROM categories ORDER BY name").fetchall(); c.close()
    return render_template("categories.html",rows=rows)

@app.route("/inventory/docs",methods=["GET","POST"])
def stock_docs():
    c=db(); ps=c.execute("SELECT * FROM products ORDER BY name").fetchall()
    if request.method=="POST":
        c.execute("INSERT INTO stock_docs(created_at,doc_type,product_id,qty,note,location) VALUES(?,?,?,?,?,?)",
                  (now(),request.form["doc_type"],request.form["product_id"],float(request.form["qty"]),request.form.get("note"),"الفرع الرئيسي"))
        c.commit(); flash("تم حفظ السند المخزني")
    rows=c.execute("""SELECT d.*,p.name product_name FROM stock_docs d LEFT JOIN products p ON p.id=d.product_id ORDER BY d.id DESC""").fetchall()
    c.close(); return render_template("stock_docs.html",rows=rows,products=ps)

@app.route("/inventory/count",methods=["GET","POST"])
def stock_count():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO stock_counts(created_at,location,status,note) VALUES(?,?,?,?)",(now(),"الفرع الرئيسي","مسودة",request.form.get("note")))
        c.commit()
    rows=c.execute("SELECT * FROM stock_counts ORDER BY id DESC").fetchall(); c.close()
    return render_template("stock_count.html",rows=rows)

@app.route("/inventory/transfer",methods=["GET","POST"])
def stock_transfer():
    c=db(); ps=c.execute("SELECT * FROM products ORDER BY name").fetchall()
    if request.method=="POST":
        c.execute("""INSERT INTO stock_transfers(created_at,from_location,to_location,product_id,qty,status) VALUES(?,?,?,?,?,'مكتمل')""",
                  (now(),request.form["from_location"],request.form["to_location"],request.form["product_id"],float(request.form["qty"])))
        c.commit()
    rows=c.execute("""SELECT t.*,p.name product_name FROM stock_transfers t JOIN products p ON p.id=t.product_id ORDER BY t.id DESC""").fetchall()
    c.close(); return render_template("stock_transfer.html",rows=rows,products=ps)

@app.route("/menu-options")
def menu_options(): return render_template("simple_page.html",title="خيارات المنيو",subtitle="إدارة خيارات المنتجات والقوائم",items=["خيارات المنتج","الإضافات Modifiers","الوجبات المجمعة"])

# ---------- PURCHASES / SUPPLIERS ----------
@app.route("/purchases",methods=["GET"])
def purchases():
    c=db()
    rows=c.execute("""SELECT pu.*,s.name supplier_name FROM purchases pu LEFT JOIN suppliers s ON s.id=pu.supplier_id ORDER BY pu.id DESC LIMIT 200""").fetchall()
    c.close(); return render_template("purchases.html",rows=rows)

@app.route("/purchases/new",methods=["GET","POST"])
def purchase_new():
    if not allowed("مشتريات"): flash("لا توجد صلاحية"); return redirect("/")
    c=db(); sups=c.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    if request.method=="POST":
        f=request.form; p=find_product(c,f.get("product_code"))
        if not p: c.close(); flash("المنتج غير موجود"); return redirect("/purchases/new")
        qty=float(f.get("qty") or 1)*float(p["mult"] or 1); cost=float(f.get("unit_cost") or 0); total=qty*cost
        status=f.get("status") or "معتمدة"; pay=f.get("payment_status") or "مدفوع"; method=f.get("payment_method") or "نقدي"
        cur=c.execute("""INSERT INTO purchases(created_at,supplier_id,invoice_no,status,payment_status,payment_method,attachment,total,location)
                         VALUES(?,?,?,?,?,?,?,?,?)""",(now(),f.get("supplier_id") or None,f.get("invoice_no"),status,pay,method,f.get("attachment"),total,"الفرع الرئيسي"))
        pid=cur.lastrowid
        c.execute("INSERT INTO purchase_items(purchase_id,product_id,qty,unit_cost,subtotal) VALUES(?,?,?,?,?)",(pid,p["id"],qty,cost,total))
        if status=="معتمدة":
            warning=cost>float(p["cost"] or 0)>0
            c.execute("UPDATE products SET stock=stock+?,cost=? WHERE id=?",(qty,cost,p["id"]))
            if f.get("supplier_id") and pay!="مدفوع": c.execute("UPDATE suppliers SET balance=balance+? WHERE id=?",(total,f.get("supplier_id")))
        c.commit(); c.close(); flash(("تنبيه: سعر الشراء أعلى من التكلفة السابقة. " if warning else "")+"تم حفظ فاتورة الشراء"); return redirect("/purchases")
    c.close(); return render_template("purchase_form.html",suppliers=sups)

@app.route("/purchase-returns",methods=["GET","POST"])
def purchase_returns():
    c=db(); sups=c.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    if request.method=="POST":
        c.execute("INSERT INTO purchase_returns(created_at,supplier_id,purchase_id,total,note) VALUES(?,?,?,?,?)",
                  (now(),request.form.get("supplier_id") or None,request.form.get("purchase_id") or None,float(request.form.get("total") or 0),request.form.get("note")))
        c.commit()
    rows=c.execute("""SELECT pr.*,s.name supplier_name FROM purchase_returns pr LEFT JOIN suppliers s ON s.id=pr.supplier_id ORDER BY pr.id DESC""").fetchall()
    c.close(); return render_template("purchase_returns.html",rows=rows,suppliers=sups)

@app.route("/suppliers",methods=["GET","POST"])
def suppliers():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO suppliers(name,phone,email,city,credit_limit) VALUES(?,?,?,?,?)",
                  (request.form["name"],request.form.get("phone"),request.form.get("email"),request.form.get("city"),float(request.form.get("credit_limit") or 0)))
        c.commit()
    q=(request.args.get("q") or "").strip()
    rows=c.execute("SELECT * FROM suppliers WHERE name LIKE ? OR phone LIKE ? ORDER BY id DESC",(f"%{q}%",f"%{q}%")).fetchall() if q else c.execute("SELECT * FROM suppliers ORDER BY id DESC").fetchall()
    c.close(); return render_template("suppliers.html",rows=rows,q=q)

@app.route("/supplier-payments",methods=["GET","POST"])
def supplier_payments():
    c=db(); sups=c.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    if request.method=="POST":
        sid=int(request.form["supplier_id"]); amt=float(request.form["amount"]); method=request.form.get("method") or "نقدي"
        c.execute("INSERT INTO supplier_payments(created_at,supplier_id,amount,method,note) VALUES(?,?,?,?,?)",(now(),sid,amt,method,request.form.get("note")))
        c.execute("UPDATE suppliers SET balance=MAX(0,balance-?) WHERE id=?",(amt,sid)); c.commit()
    rows=c.execute("""SELECT sp.*,s.name supplier_name FROM supplier_payments sp JOIN suppliers s ON s.id=sp.supplier_id ORDER BY sp.id DESC""").fetchall()
    c.close(); return render_template("supplier_payments.html",rows=rows,suppliers=sups)

# ---------- ACCOUNTING ----------
@app.route("/expenses",methods=["GET","POST"])
def expenses():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO expenses(created_at,title,category,location,amount,status,note) VALUES(?,?,?,?,?,?,?)",
                  (now(),request.form["title"],request.form.get("category"),"الفرع الرئيسي",float(request.form["amount"]),request.form.get("status") or "مدفوع",request.form.get("note")))
        c.commit(); audit("مصروف",request.form["title"])
    rows=c.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 200").fetchall(); c.close()
    return render_template("expenses.html",rows=rows)

@app.route("/fixed-assets",methods=["GET","POST"])
def fixed_assets():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO fixed_assets(name,purchase_date,cost,useful_life,note) VALUES(?,?,?,?,?)",
                  (request.form["name"],request.form.get("purchase_date"),float(request.form.get("cost") or 0),int(request.form.get("useful_life") or 0),request.form.get("note")))
        c.commit()
    rows=c.execute("SELECT * FROM fixed_assets ORDER BY id DESC").fetchall(); c.close()
    return render_template("fixed_assets.html",rows=rows)

@app.route("/journal-entries",methods=["GET","POST"])
def journal_entries():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO journal_entries(created_at,ref,entry_type,debit,credit,note,location) VALUES(?,?,?,?,?,?,?)",
                  (now(),request.form.get("ref"),request.form.get("entry_type"),float(request.form.get("debit") or 0),float(request.form.get("credit") or 0),request.form.get("note"),"الفرع الرئيسي"))
        c.commit()
    rows=c.execute("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 300").fetchall(); c.close()
    return render_template("journal_entries.html",rows=rows)

@app.route("/chart-of-accounts",methods=["GET","POST"])
def chart_accounts():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO accounts(code,name,parent_id,account_type,nature,balance) VALUES(?,?,?,?,?,?)",
                  (request.form.get("code"),request.form["name"],request.form.get("parent_id") or None,request.form.get("account_type"),request.form.get("nature"),float(request.form.get("balance") or 0)))
        c.commit()
    rows=c.execute("SELECT * FROM accounts ORDER BY code").fetchall(); c.close()
    return render_template("chart_accounts.html",rows=rows)

# ---------- REPORTS ----------
@app.route("/reports")
def reports():
    cards=[
      ("مدفوعات العملاء","حركة دفعات العملاء خلال فترة محددة"),
      ("المبيعات لكل موقع","إجمالي المبيعات حسب الموقع"),
      ("المبيعات حسب الفئات","تحليل المبيعات حسب فئات المنتجات"),
      ("المبيعات من كل فاتورة","عرض تفصيلي لكل فاتورة"),
      ("المبيعات من كل موظف","تحليل المبيعات حسب الموظف"),
      ("المبيعات لكل حالة دفع","نقدي، مدى، تحويل، آجل"),
      ("المبيعات من كل عميل","إجمالي مشتريات كل عميل"),
      ("المبيعات من كل قناة بيع","نقطة البيع والقنوات الأخرى"),
      ("معاملات العملاء","تفاصيل الحركة المالية لكل عميل"),
      ("المعاملات في كل موقع","الحركة حسب الفروع"),
      ("المنتجات المباعة للعميل","المنتجات والكميات لكل عميل"),
      ("المبيعات حسب فترة زمنية","تقرير حسب الفترة المختارة"),
      ("المبيعات حسب طرق الدفع","تفصيل طرق الدفع"),
    ]
    return render_template("reports.html",cards=cards)

# ---------- SETTINGS ----------
@app.route("/settings/company",methods=["GET","POST"])
def company_settings():
    keys=["company_name","commercial_no","tax_no","email","website","address"]
    c=db()
    if request.method=="POST":
        for k in keys:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,request.form.get(k,"")))
        c.commit(); flash("تم حفظ معلومات الشركة")
    vals={k:((c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone() or {"value":""})["value"]) for k in keys}
    c.close(); return render_template("company_settings.html",vals=vals)

@app.route("/users",methods=["GET","POST"])
def users():
    if session.get("role")!="مشرف": flash("للمشرف فقط"); return redirect("/")
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO users(username,password_hash,role,permissions) VALUES(?,?,?,?)",
                  (request.form["username"],h(request.form["password"]),request.form["role"],",".join(request.form.getlist("permissions"))))
        c.commit()
    rows=c.execute("SELECT id,username,role,permissions,active FROM users ORDER BY id DESC").fetchall()
    c.close(); return render_template("users.html",rows=rows)

@app.route("/settings/roles")
def roles(): return render_template("simple_page.html",title="الأدوار والصلاحيات",subtitle="إدارة صلاحيات المستخدمين",items=["مشرف","كاشير","مخزون","مشتريات","محاسب"])

@app.route("/settings/locations")
def locations(): return render_template("simple_page.html",title="المواقع",subtitle="إدارة الفروع والمخازن",items=["الفرع الرئيسي","+ إضافة موقع"])

@app.route("/settings/taxes")
def taxes(): return render_template("simple_page.html",title="الضرائب",subtitle="إعداد ضريبة القيمة المضافة",items=["ضريبة القيمة المضافة 15%","إعدادات الفاتورة الضريبية"])

@app.route("/settings/payments")
def payment_settings(): return render_template("simple_page.html",title="طرق الدفع",subtitle="إدارة طرق الدفع المتاحة",items=["نقدي","مدى","تحويل","آجل"])

@app.route("/settings/einvoice")
def einvoice_settings(): return render_template("simple_page.html",title="الفواتير الإلكترونية",subtitle="إعدادات الفوترة الإلكترونية",items=["إعدادات الفاتورة","الرقم الضريبي","QR"])

@app.route("/settings/import-docs")
def import_docs(): return render_template("simple_page.html",title="سندات الاستيراد",subtitle="إعدادات سندات الاستيراد",items=["سندات الاستيراد"])

@app.route("/settings/finance")
def finance_settings(): return render_template("simple_page.html",title="المالية",subtitle="إعدادات مالية عامة",items=["العملة","بداية السنة المالية","إعدادات الإقفال"])

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
