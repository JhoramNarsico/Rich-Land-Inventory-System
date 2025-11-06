#  Rich Land Auto Supply Inventory System

> A full-featured **inventory management system** for auto parts businesses, built with **Python**, **Django**, and **Bootstrap 5**. Track products, manage stock-in/stock-out transactions, view edit history, and generate PDF/CSV reports—all in one application.

---

##  Team Members

| Name                      | GitHub Profile                                      |
|--------------------------|-----------------------------------------------------|
| Jhoram Narsico           | [github.com/jhoramnarsico](https://github.com/jhoramnarsico) |
| Joseph Ernest Alberto    | [github.com/josephernestalberto](https://github.com/josephernestalberto) |
| Jillian Athea Boc        | [github.com/Jillian-Athea](https://github.com/Jillian-Athea) |
| Ram Jay Po               | [github.com/rampo](https://github.com/FunkyAtoms) |



---

##  Key Features

-  **Full CRUD** operations for products and categories  
-  **Stock tracking** with stock-in and stock-out transactions  
-  **Audit trail** for every product change (who changed what & when)  
-  **Export reports** as **PDF** (`xhtml2pdf`) or **CSV**  
-  **Responsive UI** with **Bootstrap 5**  
-  **RESTful API** with **Django REST Framework**  
-  **Interactive API docs** via **Swagger UI** (`drf-spectacular`)  
-  **Role-based access** and secure admin panel

---

## Technology Stack

### Backend
- **Language**: Python 3.8+  
- **Framework**: Django  
- **Database**: MySQL  
- **API**: Django REST Framework (DRF)

### Libraries
- `django-simple-history` → Audit logs  
- `drf-spectacular` → OpenAPI 3.0 documentation  
- `xhtml2pdf` → PDF report generation  
- `python-decouple` → Secure `.env` management  
- `PyMySQL` → MySQL database driver

### Frontend
- **Templates**: Django HTML  
- **Styling**: Bootstrap 5  
- **Interactivity**: Vanilla JavaScript + Bootstrap JS

---

##  Project Milestones (Completed ✅)

### ✅ Milestone 1 (Nov W1): Proposal & Design
- Defined `Product`, `Category`, `Transaction` models  
- Completed ITCC14 Doc (Chapters 1–2)  
- Drafted API endpoints

### ✅ Milestone 2 (Nov W2): Core Backend
- Django + MySQL + DRF setup  
- Basic CRUD + Swagger UI at `/api/docs/`

### ✅ Milestone 3 (Nov W3): Full API + Reporting
- Full CRUD with validation  
- Audit history + PDF reports  
- Seed data script added

### ✅ Milestone 4 (Nov W4): Frontend + Admin
- Responsive dashboard with Bootstrap  
- Product list, detail, history, and reporting pages  
- Admin panel enhanced with developer links

### ✅ Milestone 5 (Dec W1): Dockerization 
- `Dockerfile` and `docker-compose.yml` included  
- One-command setup for any environment

### ✅ Final (Dec W2): Demo Ready
- Live end-to-end demo prepared  
- Backup assets and slides completed

---

