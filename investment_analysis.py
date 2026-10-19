#!/usr/bin/env python3
"""Evidence-first analysis of existing scraper CSV exports; no crawling is performed here."""
import argparse
import csv
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

EXCLUDED = re.compile(r"\b(appartement|apartment|studio|duplex|étage|etage|rdc de villa|floor of villa|colocation|shared accommodation|local commercial|location saisonnière|holiday rental)\b", re.I)
STANDALONE = re.compile(r"\b(maison individuelle|maison indépendante|maison independante|maison indépendante de plain[- ]pied|independent house|standalone house|detached house|semi[- ]detached house|villa indépendante|villa independante|منزل مستقل|دار مستقلة)\b", re.I)
UNAVAILABLE = re.compile(r"\b(vendu|vendue|sold|indisponible|non disponible|unavailable)\b", re.I)
SALE_FIELDS = ["listing_title","source_website","listing_url","asking_price_tnd","governorate","city","neighborhood","advertised_property_type","standalone_status","bedrooms","built_area_m2","land_area_m2","features_condition","ownership_legal","publication_update_date","description","photo_urls","checked_at","availability_status","classification","classification_reason","estimated_total_investment_tnd","estimated_monthly_rent_tnd","rental_evidence_count","gross_yield_pct","net_yield_before_tax_pct","rental_comparable_urls"]
RENT_FIELDS = ["listing_title","source_website","listing_url","monthly_asking_rent_tnd","governorate","city","neighborhood","advertised_property_type","standalone_status","bedrooms","built_area_m2","land_area_m2","features_condition","publication_update_date","checked_at","availability_status","use_as_comparable","exclusion_reason"]
NEIGHBOR_FIELDS = ["neighborhood","median_house_sale_price_tnd","median_house_rent_tnd","gross_yield_estimate_pct","sale_listing_count","rental_listing_count","verified_standalone_sale_count","verified_standalone_rent_count","rent_at_or_above_700_pct","limitations"]
OPP_FIELDS = ["listing_title","neighborhood","sale_price_tnd","estimated_registration_fee_tnd","estimated_registry_fee_tnd","estimated_legal_admin_tnd","estimated_agency_fee_tnd","repair_contingency_tnd","initial_contingency_tnd","estimated_total_investment_tnd","budget_compliant","rent_600_gross_yield_pct","rent_700_gross_yield_pct","rent_800_gross_yield_pct","rent_900_gross_yield_pct","annual_rent_at_700_tnd","estimated_annual_net_before_tax_at_700_tnd","net_yield_before_tax_at_700_pct","simple_payback_years_at_700_tnd","classification","classification_reason","sale_listing_url","rental_comparable_urls","checked_at","assumptions"]

def val(row, *keys):
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip() not in ("", "N/A", "None", "null"):
            return str(v).strip()
    return ""

def num(value):
    s = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    if not s or s.upper() in {"N/A","NONE","NULL","N/C"}: return None
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s: return None
    if "," in s and "." not in s: s = s.replace(",", ".")
    elif "," in s and "." in s: s = s.replace(",", "")
    try: return float(s)
    except ValueError: return None

def classify(row):
    text = " ".join(val(row, k) for k in ("title","listing_title","category","property_type","advertised_property_type","description","features_condition","features"))
    if EXCLUDED.search(text): return "Excluded", "Text indicates excluded property type"
    if STANDALONE.search(text): return "Verified standalone wording", "Ad explicitly describes independent/standalone house; verify private access and exclusive occupancy"
    return "Unverified property type", "No explicit evidence that the whole property is a standalone house"

def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))

def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def neighborhood(row):
    return re.sub(r"\s+", " ", val(row,"neighborhood","city","location_raw","location").casefold()).strip()

def normalize(row, checked, is_rent):
    status, reason = classify(row)
    price = num(val(row,"price_numeric","price","price_raw"))
    currency = val(row,"currency").upper()
    if currency and currency not in {"TND","DT","DNT","TND."}: price = None
    title = val(row,"title","listing_title")
    desc = val(row,"description")
    avail = "Accessible advertisement; seller availability unconfirmed"
    if UNAVAILABLE.search(title+" "+desc): avail = "Listing text indicates sold/unavailable; exclude"
    return {
        "listing_title":title, "source_website":val(row,"source","source_website","source_domain"),
        "listing_url":val(row,"listing_url","url","announcement_url"),
        "asking_price_tnd":round(price,2) if price is not None and not is_rent else "",
        "monthly_asking_rent_tnd":round(price,2) if price is not None and is_rent else "",
        "governorate":val(row,"governorate","region"), "city":val(row,"city"),
        "neighborhood":val(row,"neighborhood","city","location_raw","location"),
        "advertised_property_type":val(row,"category","property_type","advertised_property_type") or "Not stated",
        "standalone_status":status, "bedrooms":val(row,"bedrooms","rooms","room_count"),
        "built_area_m2":val(row,"built_area_m2","built_area","surface_built","surface"),
        "land_area_m2":val(row,"land_area_m2","land_area","plot_area"),
        "features_condition":val(row,"features","options","condition"),
        "ownership_legal":val(row,"ownership","title_deed","legal_status"),
        "publication_update_date":val(row,"date_posted","publication_date","updated_at"),
        "description":desc, "photo_urls":val(row,"image_urls","photos","image_url"),
        "checked_at":checked, "availability_status":avail, "classification_reason":reason,
    }

def run(args):
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sales = [normalize(x,checked,False) for x in read_csv(args.sales_csv)]
    rents = [normalize(x,checked,True) for x in read_csv(args.rents_csv)]
    eligible_rents = []
    for r in rents:
        if r["standalone_status"] == "Verified standalone wording" and num(r["monthly_asking_rent_tnd"]) is not None and "exclude" not in r["availability_status"]:
            r["use_as_comparable"] = "Eligible wording only; verify whole-house occupancy and availability"; r["exclusion_reason"] = ""
            eligible_rents.append(r)
        else:
            r["use_as_comparable"] = "Excluded from comparable statistics"; r["exclusion_reason"] = r["classification_reason"] or r["availability_status"]
    rent_groups, sale_groups = defaultdict(list), defaultdict(list)
    for r in eligible_rents: rent_groups[neighborhood(r)].append(r)
    for s in sales:
        if num(s["asking_price_tnd"]) is not None and "exclude" not in s["availability_status"]: sale_groups[neighborhood(s)].append(s)
    opportunities = []
    for s in sales:
        price = num(s["asking_price_tnd"])
        if price is None or "exclude" in s["availability_status"]: continue
        n = neighborhood(s); comps = rent_groups.get(n, [])
        rents_n = [num(r["monthly_asking_rent_tnd"]) for r in comps]
        rents_n = [x for x in rents_n if x is not None]
        expected = median(rents_n) if len(rents_n) >= args.min_comparables else None
        repair = args.repair_allowance if re.search(r"unfinished|inachev|à finir|a finir|renov|rénover|travaux", s["description"]+" "+s["features_condition"], re.I) else 0
        reg, registry, legal, agency = (price*x for x in (args.registration_rate,args.registry_rate,args.legal_admin_rate,args.agency_rate))
        contingency = price*args.contingency_rate
        total = price+reg+registry+legal+agency+repair+contingency
        if s["standalone_status"] != "Verified standalone wording":
            cls, reason = ("Potential candidate","Standalone status unverified") if total <= args.budget else ("Rejected","Estimated all-in cost exceeds budget")
        elif total > args.budget: cls, reason = "Rejected","Estimated all-in cost exceeds budget"
        elif expected is None: cls, reason = "Insufficient data",f"Fewer than {args.min_comparables} eligible same-neighborhood whole-house rental ads"
        elif expected < args.minimum_rent: cls, reason = "Rejected","Comparable median asking rent is below target"
        else: cls, reason = "Potential candidate","Provisional screen passes; legal, condition, seller availability and rent require verification"
        yields = {f"rent_{r}_gross_yield_pct":round(r*12/total*100,2) for r in (600,700,800,900)}
        gross, net = 8400, 8400*(1-args.maintenance_rate-args.vacancy_rate)
        opp = {"listing_title":s["listing_title"],"neighborhood":s["neighborhood"],"sale_price_tnd":price,
          "estimated_registration_fee_tnd":round(reg,2),"estimated_registry_fee_tnd":round(registry,2),
          "estimated_legal_admin_tnd":round(legal,2),"estimated_agency_fee_tnd":round(agency,2),
          "repair_contingency_tnd":repair,"initial_contingency_tnd":round(contingency,2),
          "estimated_total_investment_tnd":round(total,2),"budget_compliant":"Yes" if total<=args.budget else "No",
          **yields,"annual_rent_at_700_tnd":gross,"estimated_annual_net_before_tax_at_700_tnd":round(net,2),
          "net_yield_before_tax_at_700_pct":round(net/total*100,2),"simple_payback_years_at_700_tnd":round(total/net,2) if net else "",
          "classification":cls,"classification_reason":reason,"sale_listing_url":s["listing_url"],
          "rental_comparable_urls":";".join(r["listing_url"] for r in comps),"checked_at":checked,
          "assumptions":f"registration={args.registration_rate};registry={args.registry_rate};legal_admin={args.legal_admin_rate};agency={args.agency_rate};repairs={repair};contingency={args.contingency_rate};maintenance={args.maintenance_rate};vacancy={args.vacancy_rate}; asking rents only"}
        opportunities.append(opp)
        s.update({"classification":cls,"classification_reason":reason,"estimated_total_investment_tnd":round(total,2),
          "estimated_monthly_rent_tnd":round(expected,2) if expected is not None else "",
          "rental_evidence_count":len(comps),"gross_yield_pct":round(expected*12/total*100,2) if expected is not None else "",
          "net_yield_before_tax_pct":round(expected*12*(1-args.maintenance_rate-args.vacancy_rate)/total*100,2) if expected is not None else "",
          "rental_comparable_urls":";".join(r["listing_url"] for r in comps)})
    neighborhood_rows=[]
    for n in sorted(set(sale_groups)|set(rent_groups)):
        ss, rr = sale_groups[n], rent_groups[n]
        sp=[num(s["asking_price_tnd"]) for s in ss if s["standalone_status"]=="Verified standalone wording"]
        rp=[num(r["monthly_asking_rent_tnd"]) for r in rr]
        sp=[x for x in sp if x is not None]; rp=[x for x in rp if x is not None]
        ms=median(sp) if sp else None; mr=median(rp) if rp else None
        total_proxy=ms*(1+args.registration_rate+args.registry_rate+args.legal_admin_rate+args.agency_rate+args.contingency_rate) if ms else None
        neighborhood_rows.append({"neighborhood":n,"median_house_sale_price_tnd":round(ms,2) if ms is not None else "Insufficient evidence",
          "median_house_rent_tnd":round(mr,2) if mr is not None else "Insufficient evidence",
          "gross_yield_estimate_pct":round(mr*12/total_proxy*100,2) if mr is not None and total_proxy else "Insufficient evidence",
          "sale_listing_count":len(ss),"rental_listing_count":len(rr),"verified_standalone_sale_count":len(sp),
          "verified_standalone_rent_count":len(rp),"rent_at_or_above_700_pct":round(sum(x>=700 for x in rp)/len(rp)*100,2) if rp else "Insufficient evidence",
          "limitations":"Asking prices only; exact normalized neighborhood; wording is not legal verification; small samples may be insufficient"})
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"houses_for_sale.csv",SALE_FIELDS,sales); write_csv(out/"houses_for_rent.csv",RENT_FIELDS,rents)
    write_csv(out/"neighborhood_analysis.csv",NEIGHBOR_FIELDS,neighborhood_rows); write_csv(out/"investment_opportunities.csv",OPP_FIELDS,opportunities)
    report=["# Standalone-house investment screening","",f"- Generated at (UTC): {checked}",f"- Budget: {args.budget:,.0f} TND",f"- Target rent: {args.minimum_rent:,.0f} TND/month",f"- Sale records: {len(sales)}; rental records: {len(rents)}; eligible rent-wording records: {len(eligible_rents)}","","This program analyzes existing scraper CSVs; it does not crawl or confirm availability. Standalone wording is a screening signal, not proof of title, private access, or exclusive occupancy. Asking rent is not a completed lease. Missing evidence remains insufficient.","","## Candidates",""]
    if opportunities:
        report += ["| Listing | Area | Asking price | Estimated total | Classification |","|---|---|---:|---:|---|"]
        for o in sorted(opportunities,key=lambda x:(x["classification"] not in {"Potential candidate"},x["estimated_total_investment_tnd"])):
            report.append(f'| [{o["listing_title"]}]({o["sale_listing_url"]}) | {o["neighborhood"]} | {o["sale_price_tnd"]:,.0f} | {o["estimated_total_investment_tnd"]:,.0f} | {o["classification"]} |')
    else: report.append("No sale listings with a parseable TND price were supplied.")
    report += ["","## Cost assumptions",f"- Registration {args.registration_rate:.2%}; registry {args.registry_rate:.2%}; legal/admin {args.legal_admin_rate:.2%}; agency {args.agency_rate:.2%}.",f"- Repair allowance when text signals unfinished/renovation: {args.repair_allowance:,.0f} TND; contingency {args.contingency_rate:.2%}.",f"- Maintenance {args.maintenance_rate:.2%} and vacancy {args.vacancy_rate:.2%} of gross rent.","- All fee/repair rates are configurable screening assumptions, not legal advice or professional quotes. Confirm with a Tunisian notary/lawyer and inspection quotes.",""]
    (out/"investment_report.md").write_text("\n".join(report),encoding="utf-8")
    print(f"Analysis complete: sales={len(sales)}, rents={len(rents)}, eligible_rents={len(eligible_rents)}, opportunities={len(opportunities)}, output={out}")

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sales-csv",required=True); p.add_argument("--rents-csv",required=True); p.add_argument("--output-dir",default="data/investment_analysis")
    p.add_argument("--budget",type=float,default=150000); p.add_argument("--minimum-rent",type=float,default=700); p.add_argument("--min-comparables",type=int,default=2)
    p.add_argument("--registration-rate",type=float,default=.05); p.add_argument("--registry-rate",type=float,default=.01); p.add_argument("--legal-admin-rate",type=float,default=.015); p.add_argument("--agency-rate",type=float,default=.02)
    p.add_argument("--maintenance-rate",type=float,default=.05); p.add_argument("--vacancy-rate",type=float,default=.05); p.add_argument("--repair-allowance",type=float,default=10000); p.add_argument("--contingency-rate",type=float,default=.02)
    return p

if __name__=="__main__":
    run(parser().parse_args())
