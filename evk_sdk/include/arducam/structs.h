#pragma once

#include <stdint.h>
#include <stdbool.h>

/**
 * @brief Struct representing the format of an Arducam frame.
 *
 * This struct contains information about the width, height, bit width, and format of an Arducam frame.
 */
typedef struct ARDUCAM_EVK_API ArducamFrameFormat {
    /** Width of the frame. */
    uint32_t width;
    /** Height of the frame. */
    uint32_t height;
    /** Bit width of the frame. */
    uint8_t bit_width;
    /**
     * @brief Format of the frame.
     *
     * The high 8 bits represent the pixel format(ArducamFormatMode), and the low 8 bits represent the bayer format.
     */
    uint16_t format;
} ArducamFrameFormat;

/**
 * @brief Struct representing a buffer containing an Arducam frame.
 *
 * This struct contains information about the sequence number, size, data, and format of an Arducam frame buffer.
 */
typedef struct ARDUCAM_EVK_API ArducamImageFrame {
    /** Sequence number of the frame buffer. */
    uint32_t seq;
    /** Timestamp of the frame buffer. (Unix time)
     * @note The unit of timestamp in frame is milliseconds if time source is System, otherwise 100 nanoseconds.
     */
    uint64_t timestamp;
    /** Size of the allocated memory of the frame buffer. */
    uint32_t alloc_size;
    /** Size of the expected frame buffer data. */
    uint32_t expected_size;
    /** Size of the real frame buffer data. */
    uint32_t size;
    /** Pointer to the data of the frame buffer. */
    uint8_t* data;
    /** Format of the frame buffer. */
    ArducamFrameFormat format;
} ArducamImageFrame;

/**
 * @brief Struct representing the configuration of an Arducam camera.
 *
 * This struct contains information about the width, height, bit width, format, I2C mode, and I2C address of an Arducam
 * camera.
 */
typedef struct ARDUCAM_EVK_API ArducamCameraConfig {
    char camera_name[64];
    /** Width of the camera. */
    uint32_t width;
    /** Height of the camera. */
    uint32_t height;
    /** Bit width of the camera. */
    uint8_t bit_width;
    /**
     * @brief Format of the frame.
     *
     * The upper 8 bits represent the pixel format, and the lower 8 bits represent the bayer format.
     */
    uint16_t format;
    /** I2C mode of the camera. */
    uint8_t i2c_mode;
    /** I2C address of the camera. */
    uint16_t i2c_addr;
} ArducamCameraConfig;

/**
 * @brief Struct representing an Arducam camera handle.
 *
 * This struct is a pointer to an ArducamCamera struct, which represents an Arducam camera.
 */
typedef void* ArducamCameraHandle;

/**
 * @brief Struct representing an Arducam device.
 *
 * This struct contains information about the vendor ID, product ID, usage status, serial number, USB type, and USB
 * speed of an Arducam device.
 */
typedef struct ARDUCAM_EVK_API ArducamDevice {
    /**
     * The vendor ID of the Arducam device.
     */
    const uint16_t id_vendor;
    /**
     * The product ID of the Arducam device.
     */
    const uint16_t id_product;
    /**
     * Indicates whether the Arducam device is currently in use.
     */
    const bool in_used;
    /**
     * @brief The serial number of the Arducam device.
     *
     * This field is an array of 16 bytes.
     */
    const uint8_t serial_number[16];
    /**
     * The device path of the Arducam device.
     */
    const char dev_path[256];
    /**
     * The USB type of the Arducam device.
     */
    const uint16_t usb_type;
    /**
     * The USB speed of the Arducam device.
     */
    const ArducamUSBSpeed speed;
} ArducamDevice;

/**
 * @brief Struct representing an Arducam device handle.
 *
 * A pointer to an ArducamDevice struct, which represents an Arducam device.
 */
typedef ArducamDevice* ArducamDeviceHandle;

/**
 * @brief Struct representing a list of Arducam devices.
 *
 * This struct contains information about the size of the list and a pointer to an array of ArducamDeviceHandle structs.
 */
typedef struct ARDUCAM_EVK_API ArducamDeviceList {
    /** The number of devices in the list. */
    const uint32_t size;
    /** A pointer to an array of ArducamDeviceHandle structs. */
    ArducamDeviceHandle* const devices;
} ArducamDeviceList;

/**
 * @brief Struct representing a handle to a list of Arducam devices.
 *
 * A pointer to an ArducamDeviceList struct, which contains information about the size of the list and a
 * pointer to an array of ArducamDeviceHandle structs.
 */
typedef ArducamDeviceList* ArducamDeviceListHandle;

/**
 * @brief Struct representing the parameters used to open an Arducam camera.
 *
 * This struct contains information about the configuration file name, whether the configuration file is a binary file,
 * the memory type, and the device type used to open an Arducam camera.
 */
typedef struct ARDUCAM_EVK_API ArducamCameraOpenParam {
    /** Name of the configuration file. */
    const char* config_file_name;
    /** Name of the extra configuration file. */
    const char* ext_config_file_name;
    /** Indicates whether the configuration file is a binary file. */
    bool bin_config;
    /** Memory type used to open the camera. Default: ArducamMemType::DMA. */
    ArducamMemType mem_type;
    /** Device used to open the camera. Default: null. */
    ArducamDeviceHandle device;
} ArducamCameraOpenParam;
