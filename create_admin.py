import requests

response = requests.post("http://localhost:5000/api/v1/auth/register-admin",
    json={
        "name": "Samarth",
        "email": "kharadesamarth03@gmail.com",
        "phone": "8983681903",
        "password": "Samarth@19",
        "admin_secret": "BANK_ADMIN_SECRET_2024"
    }
)
print(response.json())