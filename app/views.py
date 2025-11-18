import datetime
import json
import requests
from flask import render_template, redirect, request, flash, session, url_for
from app import app

CONNECTED_SERVICE_ADDRESS = "http://127.0.0.1:8000"

POLITICAL_PARTIES = ["Democratic Party", "Republican Party", "Socialist party"]

VALID_VOTERS = {
    "voter1": {"password": "v1pass", "voter_id": "VOID001"},
    "voter2": {"password": "v2pass", "voter_id": "VOID002"},
    "voter3": {"password": "v3pass", "voter_id": "VOID003"},
    "voter4": {"password": "v4pass", "voter_id": "VOID004"},
    "voter5": {"password": "v5pass", "voter_id": "VOID005"},
    "voter6": {"password": "v6pass", "voter_id": "VOID006"},
    "voter7": {"password": "v7pass", "voter_id": "VOID007"},
    "voter8": {"password": "v8pass", "voter_id": "VOID008"},
    "voter9": {"password": "v9pass", "voter_id": "VOID009"},
    "voter10": {"password": "v10pass", "voter_id": "VOID010"},
    "voter11": {"password": "v11pass", "voter_id": "VOID011"},
    "voter12": {"password": "v12pass", "voter_id": "VOID012"},
    "voter13": {"password": "v13pass", "voter_id": "VOID013"},
    "voter14": {"password": "v14pass", "voter_id": "VOID014"},
    "voter15": {"password": "v15pass", "voter_id": "VOID015"},

}

ADMIN_CREDENTIALS = {"admin": "adminpass"}

VOTER_IDS = [
    'VOID001','VOID002','VOID003','VOID004','VOID005',
    'VOID006','VOID007','VOID008','VOID009','VOID010',
    'VOID011','VOID012','VOID013','VOID014','VOID015'
]

vote_check = []
posts = []


def timestamp_to_string(epoch_time):
    return datetime.datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M')


def fetch_posts():
    """Fetch chain safely from node, prevent template breaking."""
    get_chain_address = f"{CONNECTED_SERVICE_ADDRESS}/chain"
    global posts

    try:
        response = requests.get(get_chain_address, timeout=3)
        response.raise_for_status()
        chain_json = response.json()
    except Exception as e:
        print("fetch_posts error:", e)
        posts = []
        return

    content = []
    for block in chain_json.get("chain", []):
        for tx in block.get("transactions", []):
            tx_item = dict(tx)
            tx_item["block_index"] = block.get("index")
            tx_item["block_hash"] = block.get("hash")
            tx_item["previous_hash"] = block.get("previous_hash")
            content.append(tx_item)

    posts = sorted(content, key=lambda x: x.get("timestamp", 0), reverse=True)


@app.route('/login', methods=['GET','POST'])
def login():
    if session.get('role') in ('voter','admin'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        uname = request.form.get('username')
        pwd = request.form.get('password')

        if uname in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[uname] == pwd:
            session['role'] = 'admin'
            session['username'] = uname
            flash("Admin login successful","ok")
            return redirect(url_for('index'))

        if uname in VALID_VOTERS and VALID_VOTERS[uname]['password'] == pwd:
            session['role'] = 'voter'
            session['username'] = uname
            session['voter_id'] = VALID_VOTERS[uname]['voter_id']
            flash("Voter login successful","ok")
            return redirect(url_for('index'))

        flash("Invalid credentials","error")
        return redirect(url_for('login'))

    return render_template("login.html", node_address=CONNECTED_SERVICE_ADDRESS)


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out","ok")
    return redirect(url_for('login'))


@app.route('/')
def index():
    # If not logged in → show login
    if session.get("role") not in ("voter", "admin"):
        return redirect(url_for("login"))

    # ------------------------------------------
    # ADMIN → Redirect to records page (home page)
    # ------------------------------------------
    if session.get("role") == "admin":
        return redirect(url_for("records"))

    # ------------------------------------------
    # VOTER → Show voting page
    # ------------------------------------------
    fetch_posts()

    vote_gain = [p.get("party") for p in posts]

    return render_template(
        "index.html",
        posts=posts,
        vote_gain=vote_gain,
        political_parties=POLITICAL_PARTIES,
        voter_ids=VOTER_IDS,
        node_address=CONNECTED_SERVICE_ADDRESS,
        readable_time=timestamp_to_string
    )



@app.route('/submit', methods=['POST'])
def submit_textarea():
    if session.get("role") != "voter":
        flash("Login as voter to vote","error")
        return redirect(url_for('login'))

    party = request.form.get("party")
    voter_id = session.get("voter_id")

    if not voter_id:
        flash("Invalid session","error")
        return redirect(url_for('login'))

    if voter_id not in VOTER_IDS:
        flash("Invalid voter ID","error")
        return redirect(url_for('index'))

    if voter_id in vote_check:
        flash("You have already voted!","error")
        return redirect(url_for('index'))

    vote_check.append(voter_id)

    post_obj = {"voter_id": voter_id, "party": party}

    try:
        requests.post(f"{CONNECTED_SERVICE_ADDRESS}/new_transaction",
                      json=post_obj, timeout=3)
    except Exception as e:
        print("TX error:", e)
        flash("Blockchain node error","error")
        return redirect(url_for('index'))

    flash(f"Vote submitted for {party}","ok")
    return redirect(url_for('index'))


@app.route('/records')
def records():
    if session.get("role") != "admin":
        flash("Admin only","error")
        return redirect(url_for('index'))

    fetch_posts()

    return render_template(
        "records.html",
        posts=posts,
        readable_time=timestamp_to_string
    )


@app.route('/results')
def result():
    if session.get("role") != "admin":
        flash("Admin only","error")
        return redirect(url_for('index'))

    try:
        resp = requests.get(f"{CONNECTED_SERVICE_ADDRESS}/results_count", timeout=3)
        counts = resp.json()
    except:
        counts = {}

    vote_counts = {p: counts.get(p, 0) for p in POLITICAL_PARTIES}

    return render_template("results.html",
                           vote_counts=vote_counts,
                           political_parties=POLITICAL_PARTIES)
@app.route('/admin_chain')
def admin_chain():
    if session.get("role") != "admin":
        return "Forbidden", 403
    try:
        resp = requests.get(f"{CONNECTED_SERVICE_ADDRESS}/chain", timeout=3)
        resp.raise_for_status()
        return resp.text  # JSON to front-end
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

