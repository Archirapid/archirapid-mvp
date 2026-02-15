```mermaid
erDiagram
    users ||--o{ plots : "publishes (as owner)"
    users ||--o{ projects : "creates (as architect)"
    users ||--o{ reservations : "makes (as client)"
    users ||--o{ client_interests : "saves"
    users ||--o{ subscriptions : "has"
    
    plots ||--o{ reservations : "receives"
    plots ||--o{ proposals : "receives"
    
    projects ||--o{ client_interests : "attracts"
    projects ||--o{ project_purchases : "sold as"
    
    reservations ||--o{ service_assignments : "requires"
    reservations ||--o{ additional_services : "involves"
    
    proposals }o--|| users : "submitted by architect"
    proposals }o--|| plots : "targets"
    
    service_assignments }o--|| service_providers : "assigned to"
    
    users {
        text id PK
        text email UK
        text name
        text role "client|architect|owner"
        integer is_professional
        text password_hash
        text phone
        text address
        text created_at
    }
    
    plots {
        integer id PK
        text title
        text catastral_ref
        real m2
        real superficie_edificable
        real lat
        real lon
        real price
        text status "disponible|reserved|sold"
        text owner_email FK
        text province
        text locality
        text photo_paths
        text vector_geojson
        text created_at
    }
    
    projects {
        integer id PK
        text title
        text architect_id FK
        real area_m2
        real m2_parcela_minima
        real price
        integer habitaciones
        integer banos
        integer plantas
        text memoria_pdf
        text cad_file
        text foto_principal
        text modelo_3d_glb
        text characteristics_json
        text created_at
    }
    
    reservations {
        text id PK
        integer plot_id FK
        text buyer_name
        text buyer_email FK
        real amount
        text kind "reserve|purchase"
        text created_at
    }
    
    client_interests {
        integer id PK
        text client_email FK
        integer project_id FK
        text created_at
    }
    
    proposals {
        text id PK
        integer plot_id FK
        text architect_id FK
        text message
        real price
        text status
        text created_at
    }
    
    subscriptions {
        text id PK
        text architect_id FK
        text plan_type "basic|pro|premium"
        real price
        integer monthly_proposals_limit
        real commission_rate
        text status "active|expired"
        text start_date
        text end_date
        text created_at
    }
    
    project_purchases {
        text id PK
        integer project_id FK
        text buyer_email FK
        real price
        integer includes_cad
        integer includes_memoria
        text created_at
    }
    
    service_providers {
        text id PK
        text name
        text email
        text service_type "constructor|surveyor"
        text phone
        text province
        real rating
        text created_at
    }
    
    service_assignments {
        text id PK
        text reservation_id FK
        text provider_id FK
        text service_type
        text status
        text created_at
    }
    
    additional_services {
        text id PK
        text reservation_id FK
        text service_type
        text description
        real price
        text status
        text created_at
    }
```

## Leyenda

### Tipos de relaciones
- `||--o{` : Uno a muchos (obligatorio a opcional)
- `}o--||` : Muchos a uno (opcional a obligatorio)

### Cardinalidades
- **users → plots**: Un propietario puede publicar muchas fincas
- **users → projects**: Un arquitecto puede crear muchos proyectos
- **users → reservations**: Un cliente puede hacer muchas reservas
- **plots → reservations**: Una finca puede tener muchas reservas (histórico)
- **projects → client_interests**: Un proyecto puede ser guardado por muchos clientes

### Estados de tablas
- **🟢 Activas con datos**: users, plots, projects, reservations, client_interests, architects, owners
- **🟡 Preparadas (vacías)**: proposals, subscriptions, payments, project_purchases, service_providers, service_assignments, additional_services
- **🔴 Legacy (deprecadas)**: proyectos, arquitectos, ventas_proyectos

### Notas de implementación
1. **Foreign Keys**: Actualmente no enforced en SQLite (usar PRAGMA foreign_keys=ON)
2. **Duplicación**: Tablas `architects` y `owners` duplican datos de `users`
3. **Email como FK**: Se usa email en vez de user_id en varios lugares (considerar cambio)
4. **Status tracking**: plots.status y reservations.kind controlan flujo de venta
