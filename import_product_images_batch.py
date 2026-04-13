import argparse
import base64
import csv
import os
import sys
import time
import urllib.request
import xmlrpc.client
from collections import defaultdict


DEFAULT_CSV_PATH = "/Users/jainiljoshi/workspace/odoo/19.2/custom/products_export_1 (1).csv"
DEFAULT_URL = "http://127.0.0.1:2222"
DEFAULT_DB = "tynor_australia_stage"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import Shopify CSV product images into Odoo product.template/product.image."
    )
    parser.add_argument("--csv-path", default=DEFAULT_CSV_PATH)
    parser.add_argument("--url", default=os.getenv("ODOO_URL", DEFAULT_URL))
    parser.add_argument("--db", default=os.getenv("ODOO_DB", DEFAULT_DB))
    parser.add_argument("--username", default=os.getenv("ODOO_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password", default=os.getenv("ODOO_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--execute", action="store_true", help="Actually write data to Odoo.")
    parser.add_argument(
        "--set-main-image",
        action="store_true",
        help="Set product.template image_1920 from first image when main image is missing.",
    )
    parser.add_argument(
        "--include-handles-with-media",
        action="store_true",
        help="Also process templates that already have website media in Extra Product Media.",
    )
    parser.add_argument("--limit-handles", type=int, default=0, help="Process only first N handles.")
    parser.add_argument("--only-handle", default="", help="Process only one handle.")
    parser.add_argument("--timeout", type=int, default=20, help="Image download timeout in seconds.")
    parser.add_argument(
        "--unmatched-report",
        default="/Users/jainiljoshi/workspace/odoo/19.2/custom/image_import_unmatched_handles.csv",
    )
    return parser.parse_args()


def connect_odoo(url, db, username, password):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise RuntimeError("Authentication failed.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models


def search_read_all(models, db, uid, password, model, domain, fields, batch_size=500):
    all_records = []
    offset = 0
    while True:
        records = models.execute_kw(
            db,
            uid,
            password,
            model,
            "search_read",
            [domain],
            {"fields": fields, "offset": offset, "limit": batch_size},
        )
        if not records:
            break
        all_records.extend(records)
        offset += len(records)
        if len(records) < batch_size:
            break
    return all_records


def parse_shopify_csv(csv_path, only_handle=""):
    handle_images = defaultdict(list)
    handle_skus = defaultdict(set)
    seen_per_handle = defaultdict(set)
    total_rows = 0
    rows_with_images = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            handle = (row.get("Handle") or "").strip()
            sku = (row.get("Variant SKU") or "").strip()
            image_src = (row.get("Image Src") or "").strip()
            image_position_raw = (row.get("Image Position") or "").strip()
            image_alt = (row.get("Image Alt Text") or "").strip()

            if only_handle and handle != only_handle:
                continue
            if not handle:
                continue

            if sku:
                handle_skus[handle].add(sku)

            if not image_src:
                continue

            rows_with_images += 1
            if image_src in seen_per_handle[handle]:
                continue
            seen_per_handle[handle].add(image_src)

            try:
                position = int(image_position_raw) if image_position_raw else 9999
            except ValueError:
                position = 9999
            handle_images[handle].append(
                {"url": image_src, "position": position, "alt": image_alt}
            )

    for handle in handle_images:
        handle_images[handle].sort(key=lambda x: (x["position"], x["url"]))

    return handle_images, handle_skus, total_rows, rows_with_images


def build_handle_template_map(models, db, uid, password, handles, handle_skus):
    handle_template_id = {}
    ambiguous_handles = {}
    sku_matched = 0

    all_skus = sorted({sku for h in handles for sku in handle_skus.get(h, set()) if sku})
    sku_to_templates = defaultdict(set)
    if all_skus:
        products = search_read_all(
            models,
            db,
            uid,
            password,
            "product.product",
            [("default_code", "in", all_skus)],
            ["id", "default_code", "product_tmpl_id"],
        )
        for p in products:
            sku = p.get("default_code")
            tmpl = p.get("product_tmpl_id")
            if sku and tmpl:
                sku_to_templates[sku].add(tmpl[0])

    for handle in handles:
        templates = set()
        for sku in handle_skus.get(handle, set()):
            templates.update(sku_to_templates.get(sku, set()))
        if len(templates) == 1:
            handle_template_id[handle] = list(templates)[0]
            sku_matched += 1
        elif len(templates) > 1:
            ambiguous_handles[handle] = sorted(templates)

    unresolved = [h for h in handles if h not in handle_template_id and h not in ambiguous_handles]
    if unresolved:
        pt_fields = models.execute_kw(
            db, uid, password, "product.template", "fields_get", [], {"attributes": ["type"]}
        )
        candidate_fields = [
            "website_slug",
            "shopify_handle",
            "x_shopify_handle",
            "x_studio_shopify_handle",
            "handle",
        ]
        fallback_fields = [
            name
            for name, meta in pt_fields.items()
            if "handle" in name.lower() and meta.get("type") in {"char", "text"}
        ]
        for fld in fallback_fields:
            if fld not in candidate_fields:
                candidate_fields.append(fld)

        for fld in candidate_fields:
            if fld not in pt_fields:
                continue
            left = [h for h in unresolved if h not in handle_template_id]
            if not left:
                break
            for handle in left:
                recs = models.execute_kw(
                    db,
                    uid,
                    password,
                    "product.template",
                    "search_read",
                    [[(fld, "=", handle)]],
                    {"fields": ["id"], "limit": 2},
                )
                if len(recs) == 1:
                    handle_template_id[handle] = recs[0]["id"]
                elif len(recs) > 1:
                    ambiguous_handles[handle] = [r["id"] for r in recs]

    return handle_template_id, ambiguous_handles, sku_matched


def download_image(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def write_unmatched_report(path, unmatched, ambiguous):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["handle", "status", "details"])
        for h in sorted(unmatched):
            writer.writerow([h, "unmatched", ""])
        for h, ids in sorted(ambiguous.items()):
            writer.writerow([h, "ambiguous", ",".join(str(x) for x in ids)])


def import_images(args):
    print(f"Connecting to Odoo: {args.url} / DB: {args.db}")
    uid, models = connect_odoo(args.url, args.db, args.username, args.password)
    print(f"Authenticated as user id {uid}")

    handle_images, handle_skus, total_rows, rows_with_images = parse_shopify_csv(
        args.csv_path, only_handle=args.only_handle.strip()
    )
    handles = sorted(handle_images.keys())
    if args.limit_handles and args.limit_handles > 0:
        handles = handles[: args.limit_handles]

    print(f"CSV rows read: {total_rows}")
    print(f"Rows with Image Src: {rows_with_images}")
    print(f"Handles with images: {len(handles)}")

    handle_template_id, ambiguous, sku_matched = build_handle_template_map(
        models, args.db, uid, args.password, handles, handle_skus
    )
    unmatched = [h for h in handles if h not in handle_template_id and h not in ambiguous]
    write_unmatched_report(args.unmatched_report, unmatched, ambiguous)

    print(f"Matched via SKU/handle fields: {len(handle_template_id)} (SKU direct: {sku_matched})")
    print(f"Unmatched handles: {len(unmatched)}")
    print(f"Ambiguous handles: {len(ambiguous)}")
    print(f"Unmatched report written: {args.unmatched_report}")

    if not args.execute:
        print("Dry-run mode: no changes were made. Use --execute to import.")
        return

    matched_template_ids = sorted(set(handle_template_id.values()))
    template_rows = search_read_all(
        models,
        args.db,
        uid,
        args.password,
        "product.template",
        [("id", "in", matched_template_ids)],
        ["id", "image_1920", "product_template_image_ids"],
    )
    template_meta = {r["id"]: r for r in template_rows}

    created_images = 0
    skipped_existing = 0
    skipped_has_media = 0
    skipped_count_covered = 0
    failed_downloads = 0
    failed_creates = 0
    set_main_count = 0
    processed_handles = 0

    for idx, handle in enumerate(handles, start=1):
        tmpl_id = handle_template_id.get(handle)
        if not tmpl_id:
            continue

        images = handle_images.get(handle, [])
        if not images:
            continue

        tmpl_meta = template_meta.get(tmpl_id, {})
        existing_media_ids = tmpl_meta.get("product_template_image_ids") or []
        has_main_image = bool(tmpl_meta.get("image_1920"))
        if existing_media_ids and not args.include_handles_with_media:
            skipped_has_media += 1
            continue

        processed_handles += 1
        print(f"[{idx}/{len(handles)}] Handle: {handle} -> template {tmpl_id}, images: {len(images)}")

        existing_image_rows = search_read_all(
            models,
            args.db,
            uid,
            args.password,
            "product.image",
            [("product_tmpl_id", "=", tmpl_id)],
            ["id", "name", "sequence"],
        )
        existing_names = {r.get("name") for r in existing_image_rows if r.get("name")}
        existing_sequences = {r.get("sequence") for r in existing_image_rows if r.get("sequence") is not None}

        # If a template already has enough website-media rows, avoid recreating the full set.
        if args.include_handles_with_media and len(existing_image_rows) >= len(images):
            skipped_count_covered += 1
            continue

        for pos, image_meta in enumerate(images, start=1):
            url = image_meta["url"]
            sequence = image_meta["position"] if image_meta["position"] != 9999 else pos
            name = image_meta["alt"] or url

            if name in existing_names or sequence in existing_sequences:
                skipped_existing += 1
                continue

            try:
                binary = download_image(url, timeout=args.timeout)
            except Exception as exc:
                failed_downloads += 1
                print(f"  - download failed: {url} ({exc})")
                continue

            img_b64 = base64.b64encode(binary).decode()
            vals = {
                "product_tmpl_id": tmpl_id,
                "name": name,
                "sequence": sequence,
                "image_1920": img_b64,
            }
            try:
                models.execute_kw(args.db, uid, args.password, "product.image", "create", [vals])
                created_images += 1
                existing_names.add(name)
                existing_sequences.add(sequence)
                if args.set_main_image and pos == 1 and not has_main_image:
                    models.execute_kw(
                        args.db,
                        uid,
                        args.password,
                        "product.template",
                        "write",
                        [[tmpl_id], {"image_1920": img_b64}],
                    )
                    set_main_count += 1
                    has_main_image = True
            except Exception as exc:
                failed_creates += 1
                print(f"  - create failed for {url} ({exc})")

    post_template_rows = search_read_all(
        models,
        args.db,
        uid,
        args.password,
        "product.template",
        [("id", "in", matched_template_ids)],
        ["id", "product_template_image_ids", "image_1920"],
    )
    templates_with_media = sum(1 for r in post_template_rows if r.get("product_template_image_ids"))
    templates_without_media = len(post_template_rows) - templates_with_media

    print("Import summary")
    print(f"Processed matched handles: {processed_handles}")
    print(f"Created product.image records: {created_images}")
    print(f"Set main template image_1920: {set_main_count}")
    print(f"Skipped handles already having website media: {skipped_has_media}")
    print(f"Skipped handles already covered by media count: {skipped_count_covered}")
    print(f"Skipped existing images: {skipped_existing}")
    print(f"Failed downloads: {failed_downloads}")
    print(f"Failed creates: {failed_creates}")
    print(f"Matched templates with website media now: {templates_with_media}/{len(post_template_rows)}")
    print(f"Matched templates still without website media: {templates_without_media}")


def main():
    args = parse_args()
    start = time.time()
    try:
        import_images(args)
    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(1)
    finally:
        print(f"Finished in {round(time.time() - start, 2)}s")


if __name__ == "__main__":
    main()
