import os
from datetime import date
from decimal import Decimal, InvalidOperation

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for

from db import (
    create_asset,
    decommission_asset,
    delete_asset,
    get_asset,
    get_assets,
    get_filter_options,
    initialize_database,
    update_asset,
)

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
VALID_STATUSES = {"Active", "In repair", "Retired", "Decommissioned"}


def form_values():
    return {
        "asset_tag": request.form.get("asset_tag", "").strip(),
        "hostname": request.form.get("hostname", "").strip(),
        "ip_address": request.form.get("ip_address", "").strip(),
        "operating_system": request.form.get("operating_system", "").strip(),
        "cpu": request.form.get("cpu", "").strip(),
        "ram_gb": request.form.get("ram_gb", "").strip() or None,
        "asset_type": request.form.get("asset_type", "").strip(),
        "location": request.form.get("location", "").strip(),
        "assigned_user": request.form.get("assigned_user", "").strip() or None,
        "purchase_date": request.form.get("purchase_date", "").strip() or None,
        "warranty_expiry": request.form.get("warranty_expiry", "").strip() or None,
        "status": request.form.get("status", "Active").strip(),
        "notes": request.form.get("notes", "").strip() or None,
    }


def validate_form_values(values):
    required_fields = (
        "asset_tag",
        "hostname",
        "ip_address",
        "operating_system",
        "asset_type",
        "location",
    )
    if any(not values[field] for field in required_fields):
        return "Complete all required asset fields."
    if values["status"] not in VALID_STATUSES:
        return "Choose a valid asset status."
    if values["ram_gb"]:
        try:
            values["ram_gb"] = Decimal(values["ram_gb"])
            if values["ram_gb"] < 0:
                return "Memory cannot be negative."
        except InvalidOperation:
            return "Memory must be a number."
    for field in ("purchase_date", "warranty_expiry"):
        if values[field]:
            try:
                date.fromisoformat(values[field])
            except ValueError:
                return "Enter dates in YYYY-MM-DD format."
    return None


@app.route("/")
def index():
    filters = {
        "search": request.args.get("search", "").strip(),
        "asset_type": request.args.get("asset_type", "").strip(),
        "location": request.args.get("location", "").strip(),
        "status": request.args.get("status", "").strip(),
    }
    assets = get_assets(filters)
    return render_template(
        "index.html",
        assets=assets,
        filters=filters,
        filter_options=get_filter_options(),
    )


@app.route("/assets/new", methods=["GET", "POST"])
def create_asset_view():
    if request.method == "POST":
        values = form_values()
        validation_error = validate_form_values(values)
        if validation_error:
            flash(validation_error, "error")
            return render_template("asset_form.html", asset=values, mode="Create"), 400
        try:
            create_asset(values)
        except mysql.connector.IntegrityError:
            flash("That asset tag is already in use. Choose a unique tag.", "error")
            return render_template("asset_form.html", asset=values, mode="Create"), 409
        flash("Asset added.", "success")
        return redirect(url_for("index"))
    return render_template("asset_form.html", asset=None, mode="Create")


@app.route("/assets/<asset_key>")
def asset_details(asset_key):
    asset = get_asset(asset_key)
    if asset is None:
        abort(404)
    return render_template("asset_details.html", asset=asset)


@app.route("/assets/<asset_key>/edit", methods=["GET", "POST"])
def edit_asset(asset_key):
    asset = get_asset(asset_key)
    if asset is None:
        abort(404)
    if request.method == "POST":
        values = form_values()
        validation_error = validate_form_values(values)
        if validation_error:
            flash(validation_error, "error")
            return render_template("asset_form.html", asset=values, mode="Update"), 400
        try:
            update_asset(asset_key, values)
        except mysql.connector.IntegrityError:
            flash("That asset tag is already in use. Choose a unique tag.", "error")
            return render_template("asset_form.html", asset=values, mode="Update"), 409
        flash("Asset updated.", "success")
        return redirect(url_for("asset_details", asset_key=asset_key))
    return render_template("asset_form.html", asset=asset, mode="Update")


@app.route("/assets/<asset_key>/decommission", methods=["POST"])
def decommission_asset_view(asset_key):
    if get_asset(asset_key) is None:
        abort(404)
    decommission_asset(asset_key)
    flash("Asset marked as decommissioned.", "success")
    return redirect(url_for("asset_details", asset_key=asset_key))


@app.route("/assets/<asset_key>/delete", methods=["POST"])
def delete_asset_view(asset_key):
    if get_asset(asset_key) is None:
        abort(404)
    delete_asset(asset_key)
    flash("Asset deleted.", "success")
    return redirect(url_for("index"))


initialize_database()


if __name__ == "__main__":
    app.run(host="localhost", port=5000, debug=True)