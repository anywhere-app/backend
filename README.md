notes:
sprvu posty maju len jeden subor (video, fotka atd)

### O commitoch a branchoch
- Ked vytvarate novy brach, tak robte vo fromate:
  - feature/branch-topic - ked ide o feature
  - fix/branch-topic - ked ide o fix
- Ked robite commit, tak piste zmysluplne zmeby, aby sa dalo rozobrat co sa zmenilo
  - feat: add ... - ked ide o nove funkcie
  - fix: fixed ... - ked ide o fixe
  - ked je to dolezite, tak za feat/fix dajte! - priklad: feat!: implement UI Kit

Tuto mozete precitat cele: https://www.conventionalcommits.org/en/v1.0.0/

endpointy:
/api/account 
- GET - get details either by id or by username (pri registracii podla emailu)
- POST - create account (distinct email, username, password hash, timestamps) alebo teda podla oauth
- PUT - update account (email, username, password, timestamps)
- DELETE - delete account (by id or username)
- GET - get all accounts 

/api/account/login
- POST - login (email, password) - vrati token, ktory sa pouziva na dalsie endpointy
- GET - get current user (vrati account, ktory je prihlaseny)

/api/locations
- GET - get all locations
- GET - get location by id alebo treba toto vobec? ved dame where dajaka podmienka
- POST - create location (name, coordinates, timestamps, desc, created_by)
- PUT - update location (name, coordinates, timestamps, desc, created_by)
- DELETE - delete location (by id)

/api/categories
- GET - get all categories or by id
- POST - create category (name, timestamps, created_by)
- PUT - update category (name, timestamps, created_by)
- DELETE - delete category 

/api/categories/{id}/locations
- GET - get all locations by category id
- myslim si ze netreba sem davat post atd lebo location updates vplyvaju aj na toto

/api/account/{id}/wishlist
- GET - get all locations in wishlist
- POST - add location to wishlist 
- DELETE - remove location from wishlist 

/api/account/{id}/visited
- GET - get all locations in visited
- POST - add location to visited 
- DELETE - remove location from visited

/api/account/{id}/posts
- GET - get all posts by account id

/api/post
- GET - get all posts or by id
- POST - create post (title, content, timestamps, created_by, location_id)
- DELETE - delete post by id
