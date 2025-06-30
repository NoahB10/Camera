#!/usr/bin/env python3
"""
Debug script to examine picamera2 camera controls structure
This helps understand how to properly access control properties
"""

def debug_camera_controls():
    """Debug camera controls structure"""
    print("🔍 Camera Controls Debug Tool")
    print("=" * 50)
    
    try:
        from picamera2 import Picamera2
        print("✅ Picamera2 import successful")
    except ImportError as e:
        print(f"❌ Picamera2 not available: {e}")
        return False
    
    # Test camera detection and controls
    for cam_id in [0, 1]:
        try:
            print(f"\n📷 Testing camera {cam_id}...")
            cam = Picamera2(cam_id)
            
            # Get camera controls
            controls = cam.camera_controls
            print(f"✅ Camera {cam_id} found - {len(controls)} controls available")
            
            # Examine structure of specific autofocus-related controls
            for control_name in ["LensPosition", "AfMode", "AfTrigger", "AfState"]:
                if control_name in controls:
                    control_obj = controls[control_name]
                    print(f"\n🔧 {control_name}:")
                    print(f"   Type: {type(control_obj)}")
                    print(f"   Value: {control_obj}")
                    
                    # Try different ways to access min/max
                    if hasattr(control_obj, 'min'):
                        print(f"   .min: {control_obj.min}")
                    if hasattr(control_obj, 'max'):
                        print(f"   .max: {control_obj.max}")
                    if hasattr(control_obj, 'default'):
                        print(f"   .default: {control_obj.default}")
                    
                    # Check if it's a tuple or list
                    if isinstance(control_obj, (tuple, list)):
                        print(f"   Length: {len(control_obj)}")
                        for i, val in enumerate(control_obj):
                            print(f"   [{i}]: {val} ({type(val)})")
                    
                    # Try to get all attributes
                    attrs = [attr for attr in dir(control_obj) if not attr.startswith('_')]
                    if attrs:
                        print(f"   Available attributes: {attrs}")
                else:
                    print(f"\n❌ {control_name}: Not available")
            
            # Also show first few general controls for reference
            print(f"\n📋 First 5 controls:")
            for i, (name, control) in enumerate(list(controls.items())[:5]):
                print(f"   {name}: {type(control)} = {control}")
            
            cam.close()
            print(f"✅ Camera {cam_id} tested successfully")
            
        except Exception as e:
            print(f"❌ Camera {cam_id} failed: {e}")
            continue
    
    return True

if __name__ == "__main__":
    debug_camera_controls() 