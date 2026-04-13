import csv
import xmlrpc.client
import zipfile
import io
import time

# Odoo XML-RPC Configuration
URL = 'http://208.87.135.47:8069'
DB = 'tynor_australia'
USERNAME = 'sales@tynor.com.au'
PASSWORD = '1Tynor2025$'

# Global tracking to prevent duplicates within the CSV itself
global_seen_emails = set()

def main():
    print(f"Connecting to Odoo at {URL} (Database: {DB})...")
    try:
        common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
        uid = common.authenticate(DB, USERNAME, PASSWORD, {})
        if not uid:
            print("Authentication failed.")
            return
        
        models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
        print(f"Successfully connected as User ID {uid}.")
    except Exception as e:
        print(f"Failed to connect to Odoo: {e}")
        return

    # Cache countries and states for fast mapping
    print("Caching Odoo countries and states...")
    countries = models.execute_kw(DB, uid, PASSWORD, 'res.country', 'search_read', [[]], {'fields': ['code', 'id']})
    country_map = {c['code']: c['id'] for c in countries if c.get('code')}

    states = models.execute_kw(DB, uid, PASSWORD, 'res.country.state', 'search_read', [[]], {'fields': ['code', 'id', 'country_id']})
    state_map = {f"{s['country_id'][0]}_{s['code']}": s['id'] for s in states if s.get('code') and s.get('country_id')}

    zip_path = '/Users/jainiljoshi/workspace/odoo/19.2/custom/customers_export.zip'
    csv_filename = 'customers_export.csv'

    print(f"Opening memory stream for {zip_path}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            with z.open(csv_filename, 'r') as f:
                io_wrapper = io.TextIOWrapper(f, encoding='utf-8-sig')
                reader = csv.DictReader(io_wrapper)
                
                batch_size = 500
                batch_records = []
                batch_emails = []
                total_processed = 0

                for row_idx, row in enumerate(reader):
                    email = row.get('Email', '').strip().lower()
                    if not email or email in global_seen_emails:
                        continue # Skip empty emails or duplicates within the CSV
                    
                    global_seen_emails.add(email)
                    
                    # Data Mapping
                    first_name = row.get('First Name', '').strip()
                    last_name = row.get('Last Name', '').strip()
                    name = f"{first_name} {last_name}".strip() or "Unnamed Customer"
                    
                    phone = row.get('Phone', '').strip() or row.get('Default Address Phone', '').strip()
                    street = row.get('Default Address Address1', '').strip()
                    street2 = row.get('Default Address Address2', '').strip()
                    city = row.get('Default Address City', '').strip()
                    zip_code = row.get('Default Address Zip', '').strip()
                    
                    country_code = row.get('Default Address Country Code', '').strip()
                    province_code = row.get('Default Address Province Code', '').strip()
                    
                    country_id = country_map.get(country_code, False)
                    state_id = False
                    if country_id and province_code:
                        state_id = state_map.get(f"{country_id}_{province_code}", False)

                    record = {
                        'name': name,
                        'email': email,
                        'phone': phone,
                        'street': street,
                        'street2': street2,
                        'city': city,
                        'zip': zip_code,
                        'country_id': country_id,
                        'state_id': state_id,
                    }
                    
                    batch_records.append(record)
                    batch_emails.append(email)

                    if len(batch_records) >= batch_size:
                        process_batch(models, DB, uid, PASSWORD, batch_records, batch_emails)
                        total_processed += len(batch_records)
                        print(f"Processed {total_processed} records.")
                        batch_records = []
                        batch_emails = []

                # Process remaining records for the final batch
                if batch_records:
                    process_batch(models, DB, uid, PASSWORD, batch_records, batch_emails)
                    total_processed += len(batch_records)
                    print(f"Processed {total_processed} records perfectly.")

        print("Import completed successfully.")

    except Exception as e:
        print(f"An error occurred reading the zip: {e}")

def process_batch(models, db, uid, pwd, records, emails):
    # Lookup existing emails in Odoo
    existing_partners = models.execute_kw(db, uid, pwd, 'res.partner', 'search_read', 
                                          [[('email', 'in', emails)]], 
                                          {'fields': ['id', 'email']})
    
    existing_map = {p['email'].lower(): p['id'] for p in existing_partners if p.get('email')}
    
    to_create = []
    skipped = 0
    
    for rec in records:
        if rec['email'].lower() in existing_map:
            # Most sensible duplicate policy: retain the existing functional Odoo partner without overwriting.
            skipped += 1
        else:
            to_create.append(rec)
            
    if to_create:
        try:
            models.execute_kw(db, uid, pwd, 'res.partner', 'create', [to_create])
            print(f"  -> Created {len(to_create)} new partners (Skipped {skipped} duplicates).")
        except Exception as e:
            print(f"  -> Error creating batch: {e}")
    else:
        print(f"  -> Skipped all {skipped} as duplicates.")

if __name__ == '__main__':
    start_time = time.time()
    main()
    print(f"Finished in {round(time.time() - start_time, 2)} seconds.")
