from flask import Flask, jsonify,request,session,send_file
from flask_cors import CORS
from otp import genotp
from cmail import sendmail
from flask_session import Session
from stoken import encode,decode
from io import BytesIO
import mysql.connector
from mysql.connector import pooling,errors

app = Flask(__name__)
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'snmproject',
    'pool_name': 'mypool',
    'pool_size': 10
}
try:
    connection_pool = pooling.MySQLConnectionPool(**db_config)
except errors.PoolError as e:
    print(f"Error creating connection pool: {e}")
    raise
#mydb=mysql.connector.connect(host='localhost',user='root',password='root',db='snmproject')
app.secret_key='codegnan@2018'
app.config['SESSION_TYPE']='filesystem'
Session(app)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})

@app.route('/')
def home():
    return jsonify({"status": "I am working"}), 200

@app.route('/api/create',methods=['POST',"GET"])
def create():
    try:
        data1 = request.get_json()
        data=data1.get('formData')
        if not data:
            return jsonify({"error": "Invalid or missing JSON payload"}), 400
        print("data:",data)
        username = data.get('user_name')
        uemail = data.get('email')
        password = data.get('password')
        print(username,uemail,password) 
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("select count(useremail) from users where useremail=%s",[uemail])
        result=cursor.fetchone() 
        print(result)
        if result[0]==0:
            gotp=genotp()
            print(gotp)
            udata={'username':username,'uemail':uemail,'password':password,'otp':gotp}
            subject="OTP for Simple Notes Manager"
            body=f"otp for registration of Simple notes manger {gotp}"
            sendmail(to=uemail,subject=subject,body=body)
            return jsonify({"success": True, "redirect_to": "/otp", "data": udata}), 200
            # return redirect(url_for('otp',enudata=encode(data=udata)))  
        else:
            return jsonify({"success": False, "message": "Email already exists"}), 409
            # return redirect(url_for('login')) 
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500  # Handle unexpected errors
    finally:
        cursor.close()
        conn.close()

@app.route('/api/otp',methods=['POST','GET'])
def otp():
    data = request.get_json()
    otpr = data.get("otpr")
    print("otp from user:",otpr)
    print(data)
    try:
        dudata = data.get("userData")
        print("dudata:",dudata)
        # dudata=decode(data=enudata)   #{'userid':userid,'username':username,'uemail':uemail,'password':password,'otp':gotp}
    except Exception as e:
        print(e)
        return jsonify({"error": "Invalid data format"}), 400
    else:
        if otpr==dudata['otp']:
            conn = connection_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("insert into users(username,useremail,password) values(%s,%s,%s)",[dudata['username'],dudata['uemail'],dudata['password']])
            conn.commit()
            return jsonify({"message": "OTP Verified Successfully"}), 200
        else:
             return jsonify({"error": "Invalid OTP"}), 400 
    finally:
        cursor.close()
        conn.close()
         
@app.route("/api/login", methods=["POST", "GET"])
def login():
    data = request.get_json()
    uemail = data.get("email")
    password = data.get("password")
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute('SELECT COUNT(useremail) FROM users WHERE useremail=%s', [uemail])
        c = cursor.fetchone()
        if c[0] == 0:
            return jsonify({"message": "Your details not exist"}), 404
        else:
            cursor.execute('SELECT password FROM users WHERE useremail=%s', [uemail])
            bpassword = cursor.fetchone()
            
            if bpassword[0].decode('utf-8') == password:  # Assuming plaintext comparison, use hashing in production
                session['user'] = uemail
                return jsonify({"message": "Login successfully", "user": session['user']}), 200
            else:
                return jsonify({"message": "Incorrect Credentials"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/api/addnotes",methods=["POST","GET"])
def addnotes():
    data1=request.get_json()
    email=data1.get('user')
    data=data1.get('addData')
    title=data.get('title')
    desc=data.get("desc")
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute("select user_id from users where useremail=%s",[email])
        id=cursor.fetchone()
        if id:
                cursor.execute('insert into notes(title,n_description,user_id) values(%s,%s,%s)',[title,desc,id[0]])
                conn.commit()
                cursor.close()
                return jsonify({"meassage":"Add Successfully"}),200
        else:
            return jsonify({"message":"something went wrong"}),500
    except mysql.connector.errors.IntegrityError:
                # flash("Duplicate Title Entry")
        return jsonify({"meassage":"Duplicate Entry"}),409
    except Exception as e:
        # Handle any other exceptions
        return jsonify({"error": str(e)}), 500
    finally:
        # Ensure resources are properly released
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route("/api/viewallnotes", methods=["POST", "GET"])
def viewallnotes():
    data = request.get_json()
    user = data['user']   
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute('select user_id from users where useremail=%s', [user])
        uid = cursor.fetchone()
        cursor.execute('select * from notes where user_id=%s', [uid[0]])
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        notes_list = [dict(zip(columns, row)) for row in result]
    except mysql.connector.errors.InterfaceError as e:
        print(f"Connection Error: {e}")
        return jsonify({"message": "Database connection error"}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "An error occurred"}), 500
    else:
        return jsonify({"message": "success", "result": notes_list}), 200
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
@app.route("/api/viewnotes",methods=["POST","GET"])
def viewnotes():
    data=request.get_json()
    nid=data['nid']
    try:
        conn=connection_pool.get_connection()
        cursor=conn.cursor(buffered=True)
        cursor.execute("select * from notes where n_id=%s",[nid])
        notes=cursor.fetchone()      
    except Exception as e:
        return jsonify({"message":str(e)}),500
    else:
        return jsonify({"message": "success","notes":notes}), 200
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
@app.route("/api/updatenotes", methods=["POST", "GET"])
def updatenotes():
    if request.method == "GET":
        nid = request.args.get("nid")
        if not nid:
            return jsonify({"message": "Note ID is required"}), 400

        try:
            conn = connection_pool.get_connection()
            cursor = conn.cursor(buffered=True)
            cursor.execute("SELECT * FROM notes WHERE n_id = %s", [nid])
            note = cursor.fetchone()
            if not note:
                return jsonify({"message": "Note not found"}), 404

            return jsonify({"message": "success", "note": {
                "id": note[0],
                "title": note[1],
                "description": note[2]
            }})

        except Exception as e:
            print(e)
            return jsonify({"message": str(e)}), 500

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    elif request.method == "POST":
        # Update note data
        data = request.get_json()
        if not data or "nid" not in data or "updateData" not in data:
            return jsonify({"message": "Invalid request format"}), 400

        nid = data["nid"]
        udata = data["updateData"]
        title = udata.get("title")
        desc = udata.get("desc")

        try:
            conn = connection_pool.get_connection()
            cursor = conn.cursor(buffered=True)

            cursor.execute("SELECT * FROM notes WHERE n_id = %s", [nid])
            note = cursor.fetchone()
            if not note:
                return jsonify({"message": "Note not found"}), 404

            cursor.execute(
                "UPDATE notes SET title = %s, n_description = %s WHERE n_id = %s",
                [title, desc, nid]
            )
            conn.commit()

            return jsonify({"message": "success"})

        except Exception as e:
            print(e)
            return jsonify({"message": str(e)}), 500

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
@app.route("/api/deletenote", methods=["POST"])
def delete_note():
    data = request.get_json()
    nid = data.get("nid")
    print("nid:",nid)
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE n_id = %s", [nid])
        conn.commit()
    except Exception as e:
        print(e)
        return jsonify({"message": "Error deleting note", "error": str(e)}), 500
    else:
        return jsonify({"message": "Note deleted successfully!"}),200
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
@app.route("/api/uploadfile",methods=['POST','GET'])
def uploadfile():
    user_id = request.form.get('id')
    try:
        filedata = request.files['file']
        print("data:",filedata)
        fname=filedata.filename
        fdata=filedata.read()
        conn = connection_pool.get_connection()
        cursor = conn.cursor()          
        cursor.execute("select user_id from users where useremail=%s",[user_id])
        id=cursor.fetchone()  
        cursor.execute("insert into filedata(fdata,filename,added_by) values(%s,%s,%s)",[fdata,fname,id[0]])
        conn.commit()
    except Exception as e:
        return jsonify({"message":str(e)}),500
    else:
        return jsonify({"message":"Success"}),200
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
            
@app.route("/api/viewallfiles",methods=['POST','GET'])
def viewallfiles():
    data = request.get_json()
    user = data['user']   
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute('select user_id from users where useremail=%s', [user])
        uid = cursor.fetchone()
        cursor.execute('select fid,filename,created_at,added_by from filedata where added_by=%s', [uid[0]])
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        files_list = [dict(zip(columns, row)) for row in result]
    except mysql.connector.errors.InterfaceError as e:
        print(f"Connection Error: {e}")
        return jsonify({"message": "Database connection error"}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "An error occurred"}), 500
    else:
        return jsonify({"message": "success", "result": files_list}), 200
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
@app.route("/api/viewfile",methods=['POST','GET'])
def viewfile():
    data=request.get_json()
    nid=data.get("nid")
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("select filename,fdata from filedata where fid=%s",[nid])
        notes=cursor.fetchone()
        bytes_data=BytesIO(notes[1])
        return send_file(bytes_data,download_name=notes[0],as_attachment=False),200
    except Exception as e:
        print(e)
        return jsonify({"message":str(e)}),500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
@app.route("/api/downloadfile", methods=['POST', 'GET'])
def downloadfile():
    try:
        data = request.get_json()
        if not data or 'nid' not in data:
            return jsonify({"message": "Invalid request data"}), 400
        
        nid = data.get("nid")
        
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT filename, fdata FROM filedata WHERE fid=%s", [nid])
        notes = cursor.fetchone()
        
        if notes is None:
            return jsonify({"message": "File not found"}), 404
        
        if notes[1] is None:
            return jsonify({"message": "File data is empty"}), 404
        
        bytes_data = BytesIO(notes[1])
        return send_file(bytes_data, download_name=notes[0], as_attachment=True), 200
    
    except Exception as e:
        print("Error in downloadfile:", e)
        return jsonify({"message": "Internal server error"}), 500
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
@app.route("/api/deletefile", methods=["POST"])
def delete_file():
    data = request.get_json()
    nid = data.get("nid")
    print(data)
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM filedata WHERE fid = %s", [nid])
        conn.commit()
    except Exception as e:
        print(e)
        return jsonify({"message": "Error deleting File", "error": str(e)}), 500
    else:
        return jsonify({"message": "File deleted successfully!"}),200
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
   
    
        
               
                


        
        
app.run(use_reloader=True, debug=True)