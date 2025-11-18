from app import app

# keep secret in environment or secure storage in production
app.secret_key = '6dbf23122cb5046cc5c0c1b245c75f8e43c59ca8ffeac292715e5078e631d0c9'
app.config['SESSION_TYPE'] = 'filesystem'

if __name__ == '__main__':
    app.run(debug=True, port=5000)
