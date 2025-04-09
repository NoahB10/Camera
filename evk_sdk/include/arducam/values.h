#pragma once

/** @internal */
/* -- ArduCamCfg->u32UsbVersion value -- */
#define USB_1   1  ///< USB 1.0
#define USB_2   2  ///< USB 2.0
#define USB_3   3  ///< USB 3.0
#define USB_3_2 4  ///< USB3.0 mode and USB2.0 interface
/** @endinternal */

/**
 * @brief Enum class representing the different I2C modes supported by the Arducam SDK.
 *
 * This enum class defines the different I2C modes supported by the Arducam SDK. The I2C mode determines the number of
 * bits used for the register address and the data in I2C transactions.
 */
typedef enum {
    I2C_MODE_8_8 = 0,   /**< 8-bit register address and 8-bit data */
    I2C_MODE_8_16 = 1,  /**< 8-bit register address and 16-bit data */
    I2C_MODE_16_8 = 2,  /**< 16-bit register address and 8-bit data */
    I2C_MODE_16_16 = 3, /**< 16-bit register address and 16-bit data */
    I2C_MODE_16_32 = 4, /**< 16-bit register address and 32-bit data */
} ArducamI2CMode;

typedef enum {
    FORMAT_MODE_RAW = 0,
    FORMAT_MODE_RGB = 1,
    FORMAT_MODE_YUV = 2,
    FORMAT_MODE_JPG = 3,
    FORMAT_MODE_MON = 4,
    FORMAT_MODE_RAW_D = 5,
    FORMAT_MODE_MON_D = 6,
    FORMAT_MODE_TOF = 7, /**< @deprecated */
    FORMAT_MODE_STATS = 8,
    FORMAT_MODE_RGB_IR = 9,
} ArducamFormatMode;

typedef enum {
    DMA = 1, /**< DMA */
    RAM = 2, /**< RAM */
} ArducamMemType;

typedef enum {
    System = 0,   /**< System: the unit of timestamp in frame is milliseconds */
    Firmware = 1, /**< Firmware: the unit of timestamp in frame is 100 nanoseconds */
} ArducamTimeSource;

typedef enum {
    trace = 0,    /**< trace */
    debug = 1,    /**< debug */
    info = 2,     /**< info */
    warn = 3,     /**< warn */
    err = 4,      /**< error */
    critical = 5, /**< critical */
    off = 6,      /**< off */
} ArducamLoggerLevel;

typedef enum {
    None = 0x00,       /**< None */
    FrameStart = 0x01, /**< Frame start */
    FrameEnd = 0x02,   /**< Frame end */
    Exit = 0x03,       /**< Exit */
    SyncTime = 0x04,   /**< Sync time */

    TransferError = 0x0100, /**< Transfer error */
    TransferTimeout,        /**< Transfer timeout */
    TransferLengthError,    /**< Transfer length error */

    DeviceConnect = 0x0200, /**< Device connect */
    UnknownDeviceConnect,   /**< Unknown Device connect */
    DeviceDisconnect,       /**< Device disconnect */
} ArducamEventCode;

typedef enum {
    Success = 0x00,  /**< 0x0000 - Success. */
    Empty = 0x10,    /**< 0x0010 - Empty. */
    InvalidArgument, /**< 0x0011 - Invalid argument. */
    NotSameDevice,   /**< 0x0012 - Not the same device. */

    ReadConfigFileFailed = 0x0101, /**< 0x0101 - Failed to read configuration file. */
    ConfigFileEmpty,               /**< 0x0102 - Configuration file is empty. */
    ConfigFormatError,             /**< 0x0103 - Camera configuration format error. */
    ControlFormatError,            /**< 0x0104 - Camera control format error. */
    OpenCameraFailed = 0x0201,     /**< 0x0201 - Failed to open camera. */
    UnknownUSBType,                /**< 0x0202 - Unknown USB type. */
    UnknownDeviceType,             /**< 0x0203 - Unknown Device type. */
    InitCameraFailed = 0x0301,     /**< 0x0301 - Failed to initialize camera. */
    MemoryAllocateFailed,          /**< 0x0302 - Failed to allocate memory. */

    USBTypeMismatch = 0x0401, /**< 0x0401 - USB type mismatch. */

    CaptureTimeout = 0x0601,  /**< 0x0601 - Capture timeout. */
    CaptureMethodConflict,    /**< 0x0602 - Capture method conflict. */
    FreeEmptyBuffer = 0x0701, /**< 0x0701 - Free empty buffer. */
    FreeUnknowBuffer,         /**< 0x0702 - Free unknown buffer. */

    RegisterMultipleCallback = 0x0801, /**< 0x0801 - Register multiple callback. */

    StateError = 0x8001, /**< 0x8001 - Camera state error. */

    NotSupported = 0xF001, /**< 0xF001 - Not support. */

    VRCommandError = 0xFF03,    /**< 0xFF03 - Vendor command error. */
    UserdataAddrError = 0xFF61, /**< 0xFF61 - Userdata address error. */
    UserdataLenError = 0xFF62,  /**< 0xFF62 - Userdata length error. */

    UnknownError = 0xFFFF, /**< 0xFFFF - Unknown error. */
} ArducamErrorCode;

typedef enum {
    USB_SPEED_UNKNOWN = 0,   /**< The OS doesn't report or know the device speed. */
    USB_SPEED_LOW = 1,       /**< The device is operating at low speed (1.5MBit/s). */
    USB_SPEED_FULL = 2,      /**< The device is operating at full speed (12MBit/s). */
    USB_SPEED_HIGH = 3,      /**< The device is operating at high speed (480MBit/s). */
    USB_SPEED_SUPER = 4,     /**< The device is operating at super speed (5000MBit/s). */
    USB_SPEED_SUPER_PLUS = 5 /**< The device is operating at super speed plus (10000MBit/s). */
} ArducamUSBSpeed;

typedef enum {
    VR_HOST_TO_DEVICE = 0x00, /**< Host to device */
    VR_DEVICE_TO_HOST = 0x80, /**< Device to host */
} ArducamVRCommandDirection;
