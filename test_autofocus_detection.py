#!/usr/bin/env python3
"""
Test script for autofocus detection and control
Tests the autofocus implementation without GUI dependencies
"""

import os
import sys
import time

def test_autofocus_detection():
    """Test autofocus detection capabilities"""
    print("🔍 Testing Autofocus Detection and Control")
    print("=" * 50)
    
    try:
        from picamera2 import Picamera2
        print("✅ Picamera2 import successful")
    except ImportError as e:
        print(f"❌ Picamera2 not available: {e}")
        print("This test requires a Raspberry Pi with Picamera2 installed")
        return False
    
    # Test camera detection
    cameras_found = []
    for cam_id in [0, 1]:
        try:
            print(f"\n📷 Testing camera {cam_id}...")
            cam = Picamera2(cam_id)
            
            # Get camera info
            try:
                camera_props = cam.camera_properties
                print(f"  Camera Properties:")
                for key, value in camera_props.items():
                    if key in ['Model', 'PixelArraySize', 'PixelArrayActiveAreas']:
                        print(f"    {key}: {value}")
            except Exception as e:
                print(f"  ⚠️  Could not read camera properties: {e}")
            
            # Test control availability
            controls = cam.camera_controls
            print(f"  Available Controls: {len(controls)} total")
            
            # Check autofocus-related controls
            autofocus_controls = []
            focus_info = {}
            
            if "LensPosition" in controls:
                lens_control = controls["LensPosition"]
                focus_info['lens_range'] = (lens_control.min, lens_control.max)
                autofocus_controls.append("LensPosition")
                print(f"    ✅ LensPosition: {lens_control.min} - {lens_control.max}")
            else:
                print(f"    ❌ LensPosition: Not available")
                
            if "AfMode" in controls:
                af_control = controls["AfMode"]
                focus_info['af_modes'] = (af_control.min, af_control.max)
                autofocus_controls.append("AfMode")
                print(f"    ✅ AfMode: {af_control.min} - {af_control.max}")
            else:
                print(f"    ❌ AfMode: Not available")
                
            if "AfTrigger" in controls:
                autofocus_controls.append("AfTrigger")
                print(f"    ✅ AfTrigger: Available")
            else:
                print(f"    ❌ AfTrigger: Not available")
                
            if "AfState" in controls:
                autofocus_controls.append("AfState")
                print(f"    ✅ AfState: Available")
            else:
                print(f"    ❌ AfState: Not available")
            
            # Determine support level
            has_manual_focus = "LensPosition" in controls and "AfMode" in controls
            has_auto_trigger = "AfTrigger" in controls
            
            if has_manual_focus:
                print(f"    🎯 Manual Focus: SUPPORTED")
                focus_info['manual_focus'] = True
            else:
                print(f"    ❌ Manual Focus: NOT SUPPORTED")
                focus_info['manual_focus'] = False
                
            if has_auto_trigger:
                print(f"    🎯 Auto Trigger: SUPPORTED")
                focus_info['auto_trigger'] = True
            else:
                print(f"    ❌ Auto Trigger: NOT SUPPORTED")
                focus_info['auto_trigger'] = False
            
            # Test basic configuration (don't start camera to avoid conflicts)
            config = cam.create_still_configuration(
                raw={"size": (4608, 2592)},
                controls={"ExposureTime": 10000, "AnalogueGain": 1.0}
            )
            print(f"    ✅ Camera configuration created successfully")
            
            cameras_found.append({
                'id': cam_id,
                'camera': cam,
                'autofocus_controls': autofocus_controls,
                'focus_info': focus_info,
                'config': config
            })
            
        except Exception as e:
            print(f"    ❌ Camera {cam_id} not available: {e}")
    
    if not cameras_found:
        print("\n❌ No cameras detected")
        return False
    
    print(f"\n✅ Found {len(cameras_found)} camera(s)")
    
    # Test focus control if available
    for cam_info in cameras_found:
        cam_id = cam_info['id']
        cam = cam_info['camera']
        focus_info = cam_info['focus_info']
        
        if focus_info.get('manual_focus', False):
            print(f"\n🧪 Testing focus control for camera {cam_id}...")
            
            try:
                # Configure and start camera for testing
                cam.configure(cam_info['config'])
                cam.start()
                time.sleep(1)  # Stabilization
                
                # Test manual focus control
                print("  Testing manual focus positions...")
                
                if focus_info.get('lens_range'):
                    min_pos, max_pos = focus_info['lens_range']
                    test_positions = [
                        min_pos + (max_pos - min_pos) * 0.2,  # Far
                        (min_pos + max_pos) / 2,              # Mid
                        min_pos + (max_pos - min_pos) * 0.8   # Near
                    ]
                else:
                    test_positions = [1.0, 5.0, 8.0]  # Default test positions
                
                for i, pos in enumerate(test_positions):
                    position_name = ["Far", "Mid", "Near"][i]
                    try:
                        cam.set_controls({"AfMode": 0, "LensPosition": pos})
                        time.sleep(0.2)
                        
                        # Read back position
                        metadata = cam.capture_metadata()
                        actual_pos = metadata.get("LensPosition", "Unknown")
                        
                        print(f"    {position_name}: Set {pos:.2f} → Actual {actual_pos}")
                        
                    except Exception as e:
                        print(f"    ❌ {position_name} position failed: {e}")
                
                # Test autofocus trigger if available
                if focus_info.get('auto_trigger', False):
                    print("  Testing autofocus trigger...")
                    try:
                        cam.set_controls({"AfMode": 1, "AfTrigger": 0})
                        time.sleep(1)  # Wait for autofocus
                        
                        metadata = cam.capture_metadata()
                        af_state = metadata.get("AfState", "Unknown")
                        lens_pos = metadata.get("LensPosition", "Unknown")
                        
                        state_names = {0: "Idle", 1: "Scanning", 2: "Focused", 3: "Failed"}
                        state_name = state_names.get(af_state, f"Unknown({af_state})")
                        
                        print(f"    Autofocus result: {state_name}, Position: {lens_pos}")
                        
                    except Exception as e:
                        print(f"    ❌ Autofocus trigger failed: {e}")
                
                cam.stop()
                print(f"  ✅ Camera {cam_id} focus testing complete")
                
            except Exception as e:
                print(f"  ❌ Camera {cam_id} focus testing failed: {e}")
                try:
                    cam.stop()
                except:
                    pass
    
    # Summary
    print(f"\n📊 Test Summary")
    print("=" * 30)
    for cam_info in cameras_found:
        cam_id = cam_info['id']
        focus_info = cam_info['focus_info']
        controls = cam_info['autofocus_controls']
        
        print(f"Camera {cam_id}:")
        print(f"  Manual Focus: {'✅' if focus_info.get('manual_focus') else '❌'}")
        print(f"  Auto Trigger: {'✅' if focus_info.get('auto_trigger') else '❌'}")
        print(f"  Controls: {', '.join(controls) if controls else 'None'}")
        
        if focus_info.get('lens_range'):
            min_pos, max_pos = focus_info['lens_range']
            print(f"  Lens Range: {min_pos} - {max_pos}")
    
    return True

if __name__ == "__main__":
    print("IMX708 Autofocus Detection Test")
    print("This script tests autofocus capabilities without the GUI")
    print()
    
    success = test_autofocus_detection()
    
    if success:
        print("\n🎉 Test completed successfully!")
        print("Your autofocus implementation should work with the detected capabilities.")
    else:
        print("\n❌ Test failed or no cameras detected.")
        print("Make sure you're running on a Raspberry Pi with camera modules connected.")
    
    print("\nTo use the enhanced GUI, run: python GUI_IMX708_Safe_Preview.py") 