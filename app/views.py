import datetime
import json
import requests
from flask import render_template, redirect, request, flash
from app import app

CONNECTED_SERVICE_ADDRESS = "http://127.0.0.1:8000"

POLITICAL_PARTIES = ["Democratic Party", "Republican Party", "Socialist party"]

VOTER_IDS = [
    'VOID001','VOID002','VOID003','VOID004','VOID005',
    'VOID006','VOID007','VOID008','VOID009','VOID010',
    'VOID011','VOID012','VOID013','VOID014','VOID015'
]

vote_check = []
posts = []


def fetch_posts():
    get_chain_address = f"{CONNECTED_SERVICE_ADDRESS}/chain"
    response = requests.get(get_chain_address)

    if response.status_code == 200:
        content = []
        chain = json.loads(response.content)

        for block in chain["chain"]:
            for tx in block["transactions"]:
                tx["index"] = block["index"]
                tx["hash"] = block["previous_hash"]
                content.append(tx)

        global posts
        posts = sorted(content, key=lambda k: k['timestamp'], reverse=True)


@app.route('/')
def index():
    fetch_posts()

    vote_gain = [p["party"] for p in posts]

    return render_template(
        'index.html',
        title='E-voting system using Blockchain',
        posts=posts,
        vote_gain=vote_gain,
        node_address=CONNECTED_SERVICE_ADDRESS,
        readable_time=timestamp_to_string,
        political_parties=POLITICAL_PARTIES,
        voter_ids=VOTER_IDS
    )


# ---------------------- FIXED SUBMIT FUNCTION --------------------------
@app.route('/submit', methods=['POST'])
def submit_textarea():

    party = request.form.get("party")
    voter_id = request.form.get("voter_id")

    post_object = {
        'voter_id': voter_id,
        'party': party,
    }

    # Validate voter
    if voter_id not in VOTER_IDS:
        flash("❌ Invalid Voter ID", "error")
        return redirect('/')

    if voter_id in vote_check:
        flash(f"❌ Voter {voter_id} has already voted!", "error")
        return redirect('/')

    vote_check.append(voter_id)

    # Submit transaction to blockchain node
    new_tx_address = f"{CONNECTED_SERVICE_ADDRESS}/new_transaction"

    requests.post(new_tx_address, json=post_object,
                  headers={'Content-type': 'application/json'})

    flash(f"✅ Voted for {party} successfully!", "success")
    return redirect('/')


# ---------------------- RECORDS PAGE ---------------------------
@app.route('/records')
def records():
    fetch_posts()
    return render_template(
        'records.html',
        title='Voting Records',
        posts=posts,
        readable_time=timestamp_to_string
    )


# ---------------------- RESULTS PAGE --------------------------
@app.route('/results')
def result():
    fetch_posts()
    vote_gain = [p.get("party") for p in posts]

    return render_template(
        'results.html',
        title='Result Summary',
        vote_gain=vote_gain,
        political_parties=POLITICAL_PARTIES
    )


def timestamp_to_string(epoch_time):
    return datetime.datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M')
