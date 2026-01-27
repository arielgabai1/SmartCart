
import requests
import sys

BASE_URL = 'http://localhost/api'

def run():
    # 0. Health Check
    try:
        h = requests.get(f"{BASE_URL.replace('/api', '')}/health")
        print(f"Health Check: {h.status_code} {h.text}")
    except Exception as e:
        print(f"Health Check failed: {e}")
        return

    # 1. Register Group (Manager)
    manager_email = f"manager_{int(time.time())}@test.com"
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "group_name": "Test Group",
        "user_name": "Manager",
        "email": manager_email,
        "password": "password"
    })
    if r.status_code != 201:
        print(f"Manager register failed: {r.status_code} {r.text}")
        return
    
    manager_data = r.json()['details']
    join_code = manager_data['join_code']
    
    # Login Manager to get token
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": manager_email, "password": "password"})
    manager_token = r.json()['token']
    
    # 2. Register Member
    member_email = f"member_{int(time.time())}@test.com"
    r = requests.post(f"{BASE_URL}/auth/join", json={
        "join_code": join_code,
        "user_name": "Member",
        "email": member_email,
        "password": "password"
    })
    if r.status_code != 201:
        print(f"Member join failed: {r.text}")
        return

    # Login Member
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": member_email, "password": "password"})
    member_token = r.json()['token']
    
    # 3. Member creates Item
    r = requests.post(f"{BASE_URL}/items", json={
        "name": "Test Item",
        "category": "TEST",
        "quantity": 1
    }, headers={"Authorization": f"Bearer {member_token}"})
    if r.status_code != 201:
        print(f"Create item failed: {r.text}")
        return
    
    item = r.json()
    item_id = item['_id']
    print(f"Item created: {item_id}")
    
    # 4. Manager Rejects Item
    r = requests.put(f"{BASE_URL}/items/{item_id}", json={
        "status": "REJECTED"
    }, headers={"Authorization": f"Bearer {manager_token}"})
    if r.status_code != 200:
        print(f"Reject item failed: {r.text}")
        return
        
    print("Item rejected by Manager")
    
    # 5. Member Deletes Item
    print("Member attempting to delete rejected item...")
    r = requests.delete(f"{BASE_URL}/items/{item_id}", 
        headers={"Authorization": f"Bearer {member_token}"})
        
    print(f"Delete response: {r.status_code}")
    print(f"Body: {r.text}")
    
    if r.status_code == 204:
        print("PASS: Member deleted item")
    else:
        print("FAIL: Member could not delete item")

import time
if __name__ == "__main__":
    run()
