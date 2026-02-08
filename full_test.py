
import requests

BASE_URL = "http://localhost:8000"

def test_pages():
    pages = [
        "/",
        "/dashboard/",
        "/planes/",
        "/diario/",
        "/progreso/",
        "/biblioteca/",
        "/perfil/",
    ]
    
    print("Testing Guest Access:")
    for page in pages:
        try:
            r = requests.get(BASE_URL + page, allow_redirects=False)
            print(f"{page}: {r.status_code}")
        except Exception as e:
            print(f"{page}: ERROR - {e}")

    print("\nTesting User Login (testuser):")
    session = requests.Session()
    # Need CSRF token
    r = session.get(BASE_URL + "/iniciar_sesion/")
    csrf_token = session.cookies.get('csrftoken')
    
    login_data = {
        'username': 'testuser',
        'password': 'testpass123',
        'csrfmiddlewaretoken': csrf_token,
        'login_submit': 'true'
    }
    r = session.post(BASE_URL + "/iniciar_sesion/", data=login_data, headers={'Referer': BASE_URL + "/iniciar_sesion/"})
    print(f"Login status: {r.status_code}")
    
    if r.status_code in [200, 302]:
        print("\nTesting User Authenticated Access:")
        for page in pages:
            r = session.get(BASE_URL + page, allow_redirects=False)
            print(f"{page}: {r.status_code}")
    
    print("\nTesting Admin Login (testadmin):")
    session_admin = requests.Session()
    r = session_admin.get(BASE_URL + "/iniciar_sesion/")
    csrf_token = session_admin.cookies.get('csrftoken')
    
    login_data = {
        'username': 'testadmin',
        'password': 'testpass123',
        'csrfmiddlewaretoken': csrf_token,
        'login_submit': 'true'
    }
    r = session_admin.post(BASE_URL + "/iniciar_sesion/", data=login_data, headers={'Referer': BASE_URL + "/iniciar_sesion/"})
    print(f"Login status: {r.status_code}")
    
    if r.status_code in [200, 302]:
        print("\nTesting Admin Authenticated Access:")
        admin_pages = [
            "/gestion-nunut/dashboard/",
            "/gestion-nunut/auditoria/",
            "/gestion-nunut/registro/",
        ]
        pages_to_test = pages + admin_pages
        for page in pages_to_test:
            r = session_admin.get(BASE_URL + page, allow_redirects=False)
            print(f"{page}: {r.status_code}")
            if r.status_code == 302:
                print(f"  -> Redirects to: {r.headers.get('Location')}")

if __name__ == "__main__":
    test_pages()
