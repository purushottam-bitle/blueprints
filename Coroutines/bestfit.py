from sqlalchemy.orm import Session
from models import TestBed, Device

def allocate_test_bed_for_suite(db: Session, required_devices: int):
    # Fetch all test beds with their unlocked devices
    test_beds = db.query(TestBed).all()

    best_fit = None

    for tb in test_beds:
        unlocked_devices = [d for d in tb.devices if not d.is_locked]
        if len(unlocked_devices) >= required_devices:
            if best_fit is None or len(unlocked_devices) < len(best_fit.devices):
                best_fit = tb
                best_fit.devices = unlocked_devices  # temp override to store available devices

    if not best_fit:
        return None, []

    # Lock the selected devices
    selected_devices = best_fit.devices[:required_devices]
    for device in selected_devices:
        device.is_locked = True
    db.commit()

    return best_fit, selected_devices


def allocate_testbed(required_devices: int, db: Session = Depends(get_db)):
    test_bed, devices = allocate_test_bed_for_suite(db, required_devices)

    if not test_bed:
        return {"error": "No suitable test bed found"}

    return {
        "test_bed": test_bed.name,
        "allocated_devices": [device.id for device in devices]
    }


def release_devices(db: Session, device_ids: List[str]):
    devices = db.query(Device).filter(Device.id.in_(device_ids)).all()
    for device in devices:
        device.is_locked = False
    db.commit()
