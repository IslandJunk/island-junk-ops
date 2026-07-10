"""Canonical enums. Contested taxonomies (job type, bin lifecycle, colour
semantics) are intentionally NOT frozen here yet — see docs/data-model.md
"Open decisions". Only settled enums live here."""
from __future__ import annotations

import enum


class Brand(str, enum.Enum):
    victoria = "victoria"
    nanaimo = "nanaimo"


class DeviceType(str, enum.Enum):
    """Set once per device at setup; the only switch on logout behaviour
    (login/sessions spec)."""
    shared_tablet = "shared_tablet"
    personal_phone = "personal_phone"


class ColourKind(str, enum.Enum):
    """What a dispatch colour means."""
    assignable = "assignable"   # a truck can be coloured this (Stage 1)
    status = "status"           # lifecycle status; Make.com keys on these; never a truck
    unassigned = "unassigned"   # sage — no truck picked yet; locked


class TruckKind(str, enum.Enum):
    hands_on = "hands_on"       # junk-removal crew truck (Trucks #3-7)
    bin = "bin"                 # roll-off bin truck


class CustomerSource(str, enum.Enum):
    seed = "seed"               # shipped seed data
    app = "app"                 # created in-app
    qb = "qb"                   # imported from a QuickBooks export


class BookingLane(str, enum.Enum):
    """The 7 real booking lanes from the booking prototype (DECIDED over the
    brief's generic 5-value type)."""
    collect = "collect"         # residential, collect on site (e-transfer)
    invoiced = "invoiced"       # commercial, invoiced
    bins = "bins"               # roll-off bin drop/pickup/swap
    pm = "pm"                   # property management
    contracts = "contracts"     # municipal / contract quick-picks
    custom = "custom"           # freeform one-off
    pallet = "pallet"           # pallet pickup


class AccountType(str, enum.Enum):
    residential = "residential"
    commercial = "commercial"
    property_mgmt = "property_mgmt"
    residential_bin = "residential_bin"


class JobStatus(str, enum.Enum):
    """Lifecycle stage. The Google colour is COMPUTED from (status + assigned truck):
    unassigned->sage, booked->truck colour, done->basil, awaiting_payment->tomato,
    unpaid->flamingo, invoiced->grape."""
    unassigned = "unassigned"
    booked = "booked"
    done = "done"
    awaiting_payment = "awaiting_payment"   # tomato — waiting e-transfer / bin returned
    unpaid = "unpaid"                       # flamingo — residential unpaid (CC or e-transfer)
    invoiced = "invoiced"                   # grape — invoiced / charged / closed


class BinAction(str, enum.Enum):
    drop = "drop"
    pickup = "pickup"
    swap = "swap"


class CustomerKind(str, enum.Enum):
    residential = "residential"
    company = "company"
    pm = "pm"
    contract = "contract"
    adhoc = "adhoc"


class BinStatus(str, enum.Enum):
    """Merged bin lifecycle (DECIDED 2026-07-09 — kept §7's reserved/full/weighing).
    `leased` and `stationed` are separate flags, not statuses."""
    idle = "idle"              # in yard, available
    reserved = "reserved"      # booked, not yet dropped
    dropped = "dropped"        # out at a job
    returning = "returning"    # en route back to yard
    returned = "returned"      # back at yard, awaiting processing
    to_sort = "to_sort"
    clearing = "clearing"      # roofing top-sort in progress
    ready_dump = "ready_dump"
    weighing = "weighing"      # at the scale
    full = "full"              # dropped and full, awaiting pickup
    maintenance = "maintenance"
    retired = "retired"        # out of service


class ContractPricing(str, enum.Enum):
    commercial = "commercial"
    hourly = "hourly"
    flatmonthly = "flatmonthly"
    flatjob = "flatjob"


class DisposalRole(str, enum.Enum):
    cost = "cost"              # we pay the facility
    income = "income"          # they pay us
    free = "free"
    sort = "sort"              # yard sort; our cost = sum of sorted streams


class PayType(str, enum.Enum):
    salaried = "salaried"
    hourly = "hourly"


class ReminderKind(str, enum.Enum):
    """`ij_reminders_v1` rows. cc_charge = the §9/§11 48-hour residential-bin
    card-charge reminder (auto-created, owner checks off; the charge stays manual)."""
    general = "general"
    cc_charge = "cc_charge"
    booking_draft = "booking_draft"   # a saved booking the manager can resume


# Access flags are stored as a text[] on employee (not a DB enum — the set can
# grow). Canonical list proposed in docs/data-model.md (resolves the 3-way
# prototype drift). Confirm before go-live.
ACCESS_FLAGS: frozenset[str] = frozenset({
    "owner", "manager", "estimate", "truck", "yard", "yardhub",
    "bin", "binreg", "maint", "hours", "swing", "reminders",
})

# Flags only the owner may grant (enforced at the logic layer, not just hidden UI).
OWNER_ONLY_GRANTABLE: frozenset[str] = frozenset({"owner", "estimate", "swing"})

