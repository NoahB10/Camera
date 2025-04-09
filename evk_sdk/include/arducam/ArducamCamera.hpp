#pragma once

#include <atomic>
#include <functional>
#include <memory>
#include <string>
#include <utility>

#ifdef BUILD_EVK_LIBRARY
#include "arducam_evk_sdk.h"
#include "optional.hpp"
#else
#include <arducam/arducam_evk_sdk.h>
#endif

/**
 * \addtogroup Api_Cpp
 * @{
 */

namespace Arducam {

using Frame = ArducamImageFrame;
using CameraConfig = ArducamCameraConfig;
using LoggerLevel = ArducamLoggerLevel;
using MemType = ArducamMemType;
using TimeSource = ArducamTimeSource;
using EventCode = ArducamEventCode;
using Errorcode = ArducamErrorCode;
using Device = ArducamDevice;
using DeviceHandle = ArducamDeviceHandle;

/**
 * @brief Enum class representing the different I2C modes supported by the Arducam SDK.
 *
 * This enum class defines the different I2C modes supported by the Arducam SDK. The I2C mode determines the number of
 * bits used for the register address and the data in I2C transactions.
 */
enum class I2CMode : uint8_t {
    I2C_MODE_8_8 = 0x00,   /**< 8-bit register address and 8-bit data */
    I2C_MODE_8_16 = 0x01,  /**< 8-bit register address and 16-bit data */
    I2C_MODE_16_8 = 0x02,  /**< 16-bit register address and 8-bit data */
    I2C_MODE_16_16 = 0x03, /**< 16-bit register address and 16-bit data */
    I2C_MODE_16_32 = 0x04, /**< 16-bit register address and 32-bit data */
};

enum class ConfigType : uint8_t {
    NONE = 0x00,   /**< No configuration */
    TEXT = 0x01,   /**< Text configuration */
    BINARY = 0x02, /**< Binary configuration */
};

/**
 * @brief A c++ wrapper for the Arducam SDK.
 *
 * @see ::ArducamCameraOpenParam
 */
struct ARDUCAM_EVK_API Param : public ArducamCameraOpenParam {
    /**
     * @brief Sets the default values for the ArducamCameraOpenParam struct.
     *
     * The default values are as follows:
     * - config_file_name: nullptr
     * - ext_config_file_name: nullptr
     * - bin_config: false
     * - mem_type: ArducamMemType::DMA
     * - device: nullptr
     *
     * @see ::ArducamDefaultParam()
     */
    Param();
};

/**
 * @brief A class representing a list of Arducam devices.
 *
 * This class provides a convenient way to manage a list of Arducam devices. It contains methods to retrieve the number
 * of devices in the list, iterate over the devices, and access individual devices by index.
 */
class ARDUCAM_EVK_API DeviceList {
   public:
    /**
     * @brief Function pointer type for a callback function to be called when an event occurs with the Arducam camera.
     *
     * @param event An ArducamEventCode enum value representing the event that occurred. (only `DeviceConnect`,
     * `DeviceDisconnect`)
     * @param device The handle to the Arducam camera device. (null if `DeviceConnect`)
     */
    using EventCallback = std::function<void(ArducamEventCode event, DeviceHandle device)>;
    /**
     * @brief Lists all Arducam devices connected to the system and returns a handle to the device list.
     *
     * This function retrieves a list of supported Arducam devices.
     * It then creates an array of device handles and populates it with the supported devices.
     * The resulting device list handle is returned to the caller.
     *
     * @return A DeviceList object containing a handle to the list of supported Arducam devices.
     *
     * @see ::ArducamListDevice()
     */
    static DeviceList listDevices();

   private:
    ArducamDeviceListHandle devices_ = nullptr;

   public:
    /**
     * @brief Default constructor for the DeviceList class.
     *
     * This constructor initializes the DeviceList object with default values.
     */
    DeviceList() = default;
    DeviceList(const DeviceList&) = delete;
    DeviceList& operator=(const DeviceList&) = delete;
    /**
     * @brief Move constructor for the DeviceList class.
     *
     * This constructor initializes the DeviceList object by moving the contents of another DeviceList object.
     * The move operation is performed in constant time and does not throw any exceptions.
     *
     * @param other The DeviceList object to move from.
     */
    DeviceList(DeviceList&& other) noexcept;
    ~DeviceList() noexcept;

    /**
     * @brief Returns a pointer to the first element of the device list.
     *
     * This function returns a pointer to the first element of the device list. The device list is a collection of
     * DeviceHandle objects representing the supported Arducam devices connected to the system.
     *
     * @return A pointer to the first element of the device list.
     */
    const DeviceHandle* begin() const;
    /**
     * @brief Returns a pointer to the element following the last element of the device list.
     *
     * This function returns a pointer to the element following the last element of the device list. The device list is
     * a collection of DeviceHandle objects representing the supported Arducam devices connected to the system.
     *
     * @return A pointer to the element following the last element of the device list.
     */
    const DeviceHandle* end() const;
    /**
     * @brief Returns the number of devices in the device list.
     *
     * This function returns the number of devices in the device list. The device list is a collection of
     * DeviceHandle objects representing the supported Arducam devices connected to the system.
     *
     * @return The number of devices in the device list.
     */
    size_t size() const;
    /**
     * @brief Returns a reference to the Arducam device handle at the specified index.
     *
     * This function returns a reference to the Arducam device handle at the specified index in the device list.
     * The device list is a collection of DeviceHandle objects representing the supported Arducam devices
     * connected to the system.
     *
     * @param index The index of the device handle to retrieve.
     * @return A reference to the Arducam device handle at the specified index.
     */
    const DeviceHandle& operator[](size_t index) const;
    /**
     * @brief Returns a reference to the Arducam device handle at the specified index.
     *
     * This function returns a reference to the Arducam device handle at the specified index in the device list.
     * The device list is a collection of DeviceHandle objects representing the supported Arducam devices
     * connected to the system.
     *
     * @param index The index of the device handle to retrieve.
     * @return A reference to the Arducam device handle at the specified index.
     * @throws std::out_of_range if the index is out of range.
     */
    const DeviceHandle& at(size_t index) const;
    /**
     * @brief Refreshes the Arducam device list.
     *
     * This function takes an Arducam device list handle and updates the list with the supported devices.
     *
     * @return true if the device list was successfully refreshed, false otherwise.
     */
    bool refresh();
    /**
     * @brief Sets the event callback function for the Arducam DeviceList.
     *
     * @param func The event callback function to set for the Arducam DeviceList. If `nullptr`, the event callback
     * function is cleared.
     *
     * @see ::ArducamDeviceListRegisterEventCallbackCpp()
     * @see ::ArducamDeviceListClearEventCallback()
     */
    bool setEventCallback(const EventCallback& func);
    /**
     * @brief Checks if an event callback function has been set for the Arducam DeviceList.
     *
     * @return `true` if an event callback function has been set for the Arducam DeviceList, `false` otherwise.
     *
     * @see ::ArducamDeviceListHasEventCallback()
     */
    bool hasEventCallback() const;
};

class ARDUCAM_EVK_API Camera {
   public:
    /**
     * Defines a function type for the capture callback used by the Arducam Camera class.
     * The capture callback function is called when a new frame is ready to be capture from the camera.
     *
     * @param data The frame buffer containing the data of the new frame.
     */
    using CaptureCallback = std::function<void(Frame data)>;
    /**
     * Defines a function type for the event callback used by the Arducam Camera class.
     * The event callback function is called when an event occurs in the camera.
     *
     * @param event The event code representing the type of event that occurred.
     */
    using EventCallback = std::function<void(ArducamEventCode event)>;
#if defined(WITH_STD_STRING_VIEW)
    /**
     * Defines a function type for the message callback used by the Arducam Camera class.
     * The message callback function is called when a log occurs in the camera.
     *
     * @param type The type of log that occurred.
     * @param message The message describing the log that occurred.
     */
    using MessageCallback = std::function<void(LoggerLevel type, std::string_view message)>;
#else
    /**
     * Defines a function type for the message callback used by the Arducam Camera class.
     * The message callback function is called when a log occurs in the camera.
     *
     * @param type The type of log that occurred.
     * @param message The message describing the log that occurred.
     * @param size The size of the message.
     */
    using MessageCallback = std::function<void(LoggerLevel type, const char* message, int size)>;
#endif

   public:
    /**
     * @brief Constructor for the Arducam Camera class.
     *
     * It sets the handle to the camera to nullptr.
     */
    Camera() = default;
    /**
     * @brief Opens an Arducam camera(device) with the given parameters.
     *   Will load the configuration file and set the camera parameters.
     *   The configuration file is optional,
     *     if it is not specified, it's required to set the camera parameters manually.
     *   The extra configuration file is optional,
     *     if it is specified, it will set the camera at `init`, `start`, `stop` and `close`.
     *
     * @param param The parameters used to open the camera.
     *
     * @see ::ArducamOpenCamera()
     */
    explicit Camera(const ArducamCameraOpenParam& param);
    /**
     * @brief Destructor for the Arducam Camera class.
     *
     * This function is the destructor for the Arducam Camera class. It is called when the object is destroyed and
     * releases any resources that were allocated by the object.
     */
    ~Camera() noexcept;

    /**
     * @brief Opens an Arducam camera(device) with the given parameters.
     *   Will load the configuration file and set the camera parameters.
     *   The configuration file is optional,
     *     if it is not specified, it's required to set the camera parameters manually.
     *   The extra configuration file is optional,
     *     if it is specified, it will set the camera at `init`, `start`, `stop` and `close`.
     *
     * @param param The parameters used to open the camera.
     *
     * @return True if the camera was opened successfully, false otherwise.
     *
     * @see ::ArducamOpenCamera()
     */
    bool open(const ArducamCameraOpenParam& param);
    /**
     * @brief Checks if the Arducam camera is currently opened.
     *
     * @return True if the camera is opened, false otherwise.
     */
    bool isOpened() const;
    /**
     * @brief Initializes the Arducam camera.
     *   Must specify the camera's width, height, bit width, and format before,
     *     if no config file is loaded.
     *   Will create the io buffers and initialize the controller.
     *   Will write the configuration file to device if it is loaded.
     *   Will write the extra configuration file to device if it is loaded.
     *
     * @return True if the camera was initialized successfully, false otherwise.
     *
     * @see ::ArducamInitCamera()
     */
    bool init();
    /**
     * @brief Get the size of available camera configurations
     *
     * @return The size of available camera configurations.
     */
    uint32_t modeSize() const;
    /**
     * @brief Lists the available camera configurations and their IDs.
     *
     * @param ids The array to store the IDs of the available camera configurations.
     * @param configs The array to store the available camera configurations.
     *
     * @note the array of ids and configs must be allocated by the caller and have a size of at least `modeSize()`.
     *
     * @return True if the camera configurations were listed successfully, false otherwise.
     *
     * @see ::ArducamListMode()
     */
    bool listMode(uint32_t* ids, ArducamCameraConfig* configs) const;
    /**
     * @brief Reloads the Arducam camera with a new configuration.
     *
     * This function reloads the camera with a new configuration specified by the `mode_id` parameter.
     * It first checks if the configuration is in binary format, and returns `false` if it is not.
     * It then loads the configuration and reloads the camera with it. It also updates the `config` of
     * the camera. Finally, it reinitializes the camera.
     *
     * @param mode_id The ID of the new configuration to load.
     *
     * @return True if the camera was successfully reloaded, false otherwise.
     *
     * @see ::ArducamSwitchMode()
     */
    bool switchMode(uint32_t mode_id);
    /**
     * @brief Clears the buffer of the Arducam camera.
     *
     * @return True if the buffer was successfully cleared, false otherwise.
     *
     * @see ::ArducamClearBuffer()
     */
    bool clearBuffer();
    /**
     * @brief Closes the Arducam camera and releases all associated resources.
     *
     * This function will stop the camera if it is running
     * This function will release the USB interface, and deinitialize the controller.
     * It also releases all buffers and deletes the handle.
     *
     * @see ::ArducamCloseCamera()
     */
    bool close();
    /**
     * @brief Starts the Arducam camera.
     *
     * This function initializes transfers, resets the event queue, and starts the poll and event threads.
     *
     * @see ::ArducamStartCamera()
     */
    bool start();
    /**
     * @brief Stops the Arducam camera and releases all associated resources.
     *
     * This function sets the `do_exit` flag to true, which signals the poll and event threads to exit.
     * It also pushes an `ArducamEventCode::Exit` event to the event queue. If the event queue is full,
     * a warning is logged and the event queue is exited forcefully. The poll and event threads are then
     * joined. The function also logs a message indicating that the camera has been stopped.
     *
     * @see ::ArducamStopCamera()
     */
    bool stop();
    /**
     * @brief Checks if the Arducam camera is connected to a USB 3.0 port.
     *
     * @return true if it is a USB 3.0 device connected to a USB 3.0 port or if it is a USB 2.0 device,
     *   otherwise false.
     *
     * @see ::ArducamCheckUSBType()
     */
    bool checkUSBType();
    /**
     * @brief Wait a frame from the Arducam camera.
     *
     * This function wait a frame from the Arducam camera. It waits for a frame to be available in the output queue for
     * a maximum of `timeout` milliseconds. If a frame is available, it is returned.
     * If no frame is available within the timeout period, the function returns an error code.
     *
     * @param timeout The maximum time to wait for a frame to be available, in milliseconds. negative value means
     * forever.
     *
     * @return true if a frame is available.
     *
     * @see ::ArducamWaitCaptureImage()
     */
    bool waitCapture(int timeout = 1500);
    /**
     * @brief Receives a frame from the Arducam camera.
     *
     * This function receives a frame from the Arducam camera. It waits for a frame to be available in the queue for a
     * maximum of `timeout` milliseconds. If a frame is available, it is returned in the `frameData` parameter and the
     * function returns true. If no frame is available within the timeout period, the function returns false.
     *
     * @param frameData The buffer to store the frame data.
     * @param timeout The maximum time to wait for a frame to be available, in milliseconds.
     *
     * @note The caller is responsible for freeing the image by calling `Camera::freeImage()`.
     *
     * @return True if the frame was read successfully, false otherwise.
     *
     * @see ::ArducamCaptureImage()
     */
    bool capture(Frame& frameData, int timeout = 1500);
    /**
     * @brief Returns a frame buffer to the input queue of the Arducam camera.
     *
     * This function returns a frame to the input queue of the Arducam camera.
     * If the frame is invalid (i.e. the `data` field is null), the function returns an error code.
     * If the size of the frame does not match the expected size of frames for the camera,
     * the function logs an error message and drops the frame. Otherwise, the frame is added to
     * the input queue of the camera.
     *
     * @param frameData The frame buffer to return to the input queue.
     *
     * @return True if the frame was successfully returned to the input queue, false otherwise.
     *
     * @see ::ArducamFreeImage()
     */
    bool freeImage(const Frame& frameData);
    /**
     * @brief Get the count of available frames in the output queue of the Arducam camera.
     *
     * @return A count of available frames in the output queue of the Arducam camera.
     *
     * @see ::ArducamAvailableImageCount()
     */
    int getAvailCount();

    /**
     * @brief Registers an array of controls for the Arducam camera.
     *
     * This function registers an array of controls for the Arducam camera. The `controls` parameter is an array of
     * `Control` structs that define the controls to be registered. The `controls_length` parameter is the length of the
     * `controls` array. The caller must keep and free the `controls` array.
     *
     * @param controls The array of controls to register.
     * @param controls_length The length of the `controls` array.
     * @return True if the controls were successfully registered, false otherwise.
     *
     * @note The caller must keep the `controls` array. It must not be freed or modified until the camera is closed.
     *
     * @see ::ArducamRegisterCtrls()
     */
    bool registerControls(Control* controls, uint32_t controls_length);
    /**
     * @brief Sets the value of a control for the Arducam camera.
     *
     * This function sets the value of a control for the Arducam camera. The `func_name` parameter is a string that
     * specifies the name of the control function to set. The `val` parameter is the value to set the control to.
     *
     * @param name The name of the control function to set.
     * @param val The value to set the control to.
     * @return True if the control was successfully set, false otherwise.
     *
     * @see ::ArducamSetCtrl()
     */
    bool setControl(const char* name, int64_t val);
    /**
     * @brief Returns a length of controls for the Arducam camera.
     *
     * @return A length of controls for the Arducam camera.
     *
     * @see ::ArducamListCtrls()
     */
    uint32_t controlSize() const;
    /**
     * @brief Returns a array of controls for the Arducam camera.
     *
     * This function returns a array of controls for the Arducam camera. The array contains `Control` structs that
     * define the controls. The caller must not modify or free the `controls` array, as ownership is not transferred.
     *
     * @return A array of `Control` structs that define the controls for the Arducam camera.
     *
     * @see ::ArducamListCtrls()
     */
    const Control* controls() const;

    /**
     * @brief Sets the time source for the Arducam camera.
     *
     * @param val The time source value, which can be either `TimeSource::Firmware` or `TimeSource::System`.
     *
     * @return True if the control was successfully set, false otherwise.
     */
    bool setTimeSource(TimeSource val);

    /**
     * @brief Enables console logging for the Arducam camera.
     *   Will set the log level to `info` if it is lower than `info`.
     *
     * @param enable A boolean value indicating whether to enable or disable console logging.
     *
     * @see ::ArducamEnableConsoleLog()
     */
    void enableConsoleLog(bool enable = true);
    /**
     * @brief Sets the log level for the Arducam camera logger.
     *
     * @param level The log level to set for the logger.
     *
     * @note The library also can read the environment variable `ARDUCAM_LOG_LEVEL` to set the log level.
     *
     * @see ::ArducamSetLogLevel()
     */
    void setLogLevel(LoggerLevel level);
    /**
     * @brief Gets the log level for the Arducam camera logger.
     *
     * @return The log level for the Arducam camera logger.
     *
     * @see ::ArducamGetLogLevel()
     */
    LoggerLevel logLevel() const;
    /**
     * Saves the log to a file for the Arducam camera.
     *
     * @param filename The name of the file to save the log to.
     *
     * @return true if the log was saved successfully, false otherwise.
     *
     * @see ::ArducamAddLogFile()
     */
    bool addLogFile(const char* filename);
    /**
     * @brief Reads board configuration data from the ArduCam USB device.
     *
     * This function reads board configuration data from the ArduCam USB device using the specified vendor command,
     * value, index, and buffer size. The `command` parameter specifies the vendor command to send, the `value`
     * parameter specifies the value to send with the command, the `index` parameter specifies the index to send with
     * the command, and the `buf_size` parameter specifies the size of the buffer to receive.
     *
     * @param command The vendor command to send.
     * @param value The value to send with the command.
     * @param index The index to send with the command.
     * @param buf_size The size of the buffer to receive.
     * @param data The buffer to receive the data.
     * @return true if the board configuration data was read successfully, false otherwise.
     *
     * @see ::ArducamReadBoardConfig()
     */
    bool readBoardConfig(uint8_t command, uint16_t value, uint16_t index, uint32_t buf_size, uint8_t* data);
    /**
     * @brief Reads user data from the ArduCam USB device.
     *
     * This function reads user data from the ArduCam USB device. The `addr` parameter specifies the starting address of
     * the user data to read, and the `len` parameter specifies the length of the user data to read.
     *
     * @param addr The starting address of the user data to read.
     * @param len The length of the user data to read.
     * @param data The buffer to receive the data.
     * @return true if the user data was read successfully, false otherwise.
     *
     * @see ::ArducamReadUserData()
     */
    bool readUserData(uint16_t addr, uint8_t len, uint8_t* data);
#if defined(WITH_STD_OPTIONAL)
    /**
     * @brief Reads a value from a register using the specified I2C mode and address.
     *
     * This function reads a value from a register using the specified I2C mode and address. The `mode` parameter
     * specifies the I2C mode to use, and the `i2cAddr` parameter specifies the I2C address to use. The `regAddr`
     * parameter specifies the address of the register to read from.
     *
     * @param mode The I2C mode to use.
     * @param i2cAddr The I2C address to use.
     * @param regAddr The address of the register to read from.
     * @return The value read from the register, or `std::nullopt` if the read operation failed.
     *
     * @see ::ArducamReadReg_8_8()
     * @see ::ArducamReadReg_8_16()
     * @see ::ArducamReadReg_16_8()
     * @see ::ArducamReadReg_16_16()
     *
     * @note This function will return a optional if the C++ standard library version is less than C++17.
     */
    std::optional<uint32_t> readReg(I2CMode mode, uint32_t i2cAddr, uint32_t regAddr);
    /**
     * @brief Reads a value from a sensor register.
     *
     * This function reads a value from a sensor register. The `regAddr` parameter specifies the address of the register
     * to read from. If the read operation is successful, the function returns the value read from the register.
     *
     * @param regAddr The address of the register to read from.
     * @return The value read from the register, or `std::nullopt` if the read operation failed.
     *
     * @see ::ArducamReadSensorReg()
     *
     * @note This function will return a optional if the C++ standard library version is less than C++17.
     */
    std::optional<uint32_t> readSensorReg(uint32_t regAddr);
#else
    /**
     * @brief Reads a value from a register using the specified I2C mode and address.
     *
     * This function reads a value from a register using the specified I2C mode and address. The `mode` parameter
     * specifies the I2C mode to use, and the `i2cAddr` parameter specifies the I2C address to use. The `regAddr`
     * parameter specifies the address of the register to read from.
     *
     * @param mode The I2C mode to use.
     * @param i2cAddr The I2C address to use.
     * @param regAddr The address of the register to read from.
     * @return The value read from the register,
     *   you may check the `lastError()` function to see if the read operation failed.
     *
     * @see ::ArducamReadReg_8_8()
     * @see ::ArducamReadReg_8_16()
     * @see ::ArducamReadReg_16_8()
     * @see ::ArducamReadReg_16_16()
     */
    uint32_t readReg(I2CMode mode, uint32_t i2cAddr, uint32_t regAddr);
    /**
     * @brief Reads a value from a sensor register.
     *
     * This function reads a value from a sensor register. The `regAddr` parameter specifies the address of the register
     * to read from. If the read operation is successful, the function returns the value read from the register.
     *
     * @param regAddr The address of the register to read from.
     * @return The value read from the register,
     *   you may check the `lastError()` function to see if the read operation failed.
     *
     * @see ::ArducamReadSensorReg()
     */
    uint32_t readSensorReg(uint32_t regAddr);
#endif
    /**
     * @brief Writes board configuration data to the ArduCam USB device.
     *
     * This function writes board configuration data to the ArduCam USB device using the specified vendor command,
     * value, index, and buffer. The `command` parameter specifies the vendor command to send, the `value` parameter
     * specifies the value to send with the command, the `index` parameter specifies the index to send with the command,
     * and the `buf` parameter specifies the buffer containing the data to write.
     *
     * @param command The vendor command to send.
     * @param value The value to send with the command.
     * @param index The index to send with the command.
     * @param buf The buffer containing the data to write.
     * @param buf_size The size of the buffer to send.
     *
     * @return `true` if the write operation was successful, `false` otherwise.
     *
     * @see ::ArducamWriteBoardConfig()
     */
    bool writeBoardConfig(uint8_t command, uint16_t value, uint16_t index, const uint8_t* buf, uint32_t buf_size);
    /**
     * @brief Writes user data to the ArduCam USB device.
     *
     * This function writes user data to the ArduCam USB device. The `addr` parameter specifies the starting address of
     * the user data to write, and the `data` parameter specifies the user data to write.
     *
     * @param addr The starting address of the user data to write.
     * @param data The user data to write.
     * @param data_size The size of the buffer to send.
     *
     * @return `true` if the write operation was successful, `false` otherwise.
     *
     * @see ::ArducamWriteUserData()
     */
    bool writeUserData(uint16_t addr, const uint8_t* data, uint32_t data_size);
    /**
     * @brief Writes a value to a register using the specified I2C mode and address.
     *
     * This function writes a value to a register using the specified I2C mode and address. The `mode` parameter
     * specifies the I2C mode to use, and the `i2cAddr` parameter specifies the I2C address to use. The `regAddr`
     * parameter specifies the address of the register to write to, and the `val` parameter specifies the value to write
     * to the register.
     *
     * @param mode The I2C mode to use.
     * @param i2cAddr The I2C address to use.
     * @param regAddr The address of the register to write to.
     * @param val The value to write to the register.
     *
     * @return `true` if the write operation was successful, `false` otherwise.
     *
     * @see ::ArducamWriteReg_8_8()
     * @see ::ArducamWriteReg_8_16()
     * @see ::ArducamWriteReg_16_8()
     * @see ::ArducamWriteReg_16_16()
     */
    bool writeReg(I2CMode mode, uint32_t i2cAddr, uint32_t regAddr, uint32_t val);

    /**
     * @brief Writes a value to a sensor register.
     *
     * This function writes a value to a sensor register. The `regAddr` parameter specifies the address of the register
     * to write to, and the `val` parameter specifies the value to write to the register. If the write operation is
     * successful, the function returns `true`. Otherwise, it returns `false`.
     *
     * @param regAddr The address of the register to write to.
     * @param val The value to write to the register.
     *
     * @return `true` if the write operation was successful, `false` otherwise.
     *
     * @see ::ArducamWriteSensorReg()
     */
    bool writeSensorReg(uint32_t regAddr, uint32_t val);

    /**
     * @brief Send a vendor request to the device.
     *
     * @param command The vendor command to send.
     * @param direction The direction to send with the command.
     * @param value The value to send with the command.
     * @param index The index to send with the command.
     * @param buf The buffer to receive or send the data.
     * @param buf_size The size of the buffer to send.
     *
     * @return `true` if the read operation was successful, `false` otherwise.
     *
     * @see ::ArducamSendVRCommand()
     */
    bool sendVRCommand(uint8_t command, uint8_t direction, uint16_t value, uint16_t index, uint8_t* buf,
                       uint32_t buf_size);

    // TODO:
    // softTrigger:
    // uint32_t softTrigger();
    // IsFrameReady:
    // uint32_t isFrameReady();

    // Callback
    /**
     * @brief Sets the capture callback function for the Arducam camera.
     *
     * This function sets the capture callback function for the Arducam camera based on the `func` parameter.
     *
     * @param func The capture callback function to set for the Arducam camera. If `nullptr`, the capture callback
     * function is cleared.
     *
     * @see ::ArducamRegisterCaptureCallbackCpp()
     * @see ::ArducamClearCaptureCallback()
     */
    void setCaptureCallback(const CaptureCallback& func);
    /**
     * @brief Checks if a capture callback function has been set for the Arducam camera.
     *
     * This function checks if a capture callback function has been set for the Arducam camera.
     *
     * @return `true` if a capture callback function has been set for the Arducam camera, `false` otherwise.
     *
     * @see ::ArducamHasCaptureCallback()
     */
    bool hasCaptureCallback() const;
    /**
     * @brief Sets the event callback function for the Arducam camera.
     *
     * This function sets the event callback function for the Arducam camera based on the `func` parameter.
     *
     * @param func The event callback function to set for the Arducam camera. If `nullptr`, the event callback function
     * is cleared.
     *
     * @see ::ArducamRegisterEventCallbackCpp()
     * @see ::ArducamClearEventCallback()
     */
    void setEventCallback(const EventCallback& func);
    /**
     * @brief Checks if an event callback function has been set for the Arducam camera.
     *
     * This function checks if an event callback function has been set for the Arducam camera.
     *
     * @return `true` if an event callback function has been set for the Arducam camera, `false` otherwise.
     *
     * @see ::ArducamHasEventCallback()
     */
    bool hasEventCallback() const;
    /**
     * @brief Sets the message callback function for the Arducam camera.
     *
     * This function sets the message callback function for the Arducam camera based on the `func` parameter.
     *
     * @param func The message callback function to set for the Arducam camera. If `nullptr`, the message callback
     * function is cleared.
     *
     * @see ::ArducamClearMessageCallback()
     */
    void setMessageCallback(const MessageCallback& func);
    /**
     * @brief Checks if an message callback function has been set for the Arducam camera.
     *
     * This function checks if an message callback function has been set for the Arducam camera.
     *
     * @return `true` if an message callback function has been set for the Arducam camera, `false` otherwise.
     *
     * @see ::ArducamHasMessageCallback()
     */
    bool hasMessageCallback() const;

    // feilds
    /**
     * @brief Gets the capture frames per second (FPS) of the Arducam camera.
     *
     * This function retrieves the capture FPS of the Arducam camera.
     *
     * @return The capture FPS of the Arducam camera.
     *
     * @see ::ArducamGetCaptureFps()
     */
    int captureFps() const;
    /**
     * @brief Gets the bandwidth of the Arducam camera.
     *
     * This function retrieves the bandwidth of the Arducam camera.
     *
     * @return The bandwidth of the Arducam camera.
     *
     * @see ::ArducamGetBandwidth()
     */
    int bandwidth() const;
#if defined(WITH_STD_STRING_VIEW)
    /**
     * Returns a string representation of the USB type used by the Arducam camera associated.
     *
     * @return A string view of the USB type used by the camera.
     *
     * @see ::ArducamGetUSBType()
     */
    std::string_view usbType() const;
#else
    /**
     * Returns a string representation of the USB type used by the Arducam camera associated.
     *
     * @return A string of the USB type used by the camera.
     *
     * @see ::ArducamGetUSBType()
     */
    const char* usbType() const;
#endif
    /**
     * Returns a integer representation of the USB type used by the Arducam camera associated.
     *
     * @return A integer of the USB type used by the camera.
     *
     * @see ::ArducamGetUSBTypeNumber()
     */
    int usbTypeNumber() const;
    /**
     * @brief Gets the current device of the Arducam camera.
     *
     * @return The current device of the Arducam camera.
     *
     * @see ::ArducamGetDeviceHandle()
     */
    DeviceHandle device() const;
    /**
     * @brief Gets the current configuration of the Arducam camera.
     *
     * @return The current configuration of the Arducam camera.
     *
     * @see ::ArducamGetCameraConfig()
     */
    ArducamCameraConfig config() const;
    /**
     * @brief Gets the config type of the Arducam camera.
     *
     * @return The config type of the Arducam camera.
     *
     * @see ::ArducamConfigLoaded()
     * @see ::ArducamBinConfigLoaded()
     */
    ConfigType configType() const;
    /**
     * @brief Sets the configuration of the Arducam camera and reloads the camera with the new configuration.
     *
     * @param config The configuration to set for the Arducam camera.
     *
     * @see ::ArducamSetCameraConfig()
     */
    bool setConfig(const ArducamCameraConfig& config);
    /**
     * @brief Sets the transfer configuration of the Arducam camera.
     *
     * This function sets the transfer configuration of the Arducam camera to the values specified in the
     * `transfer_count` and `buffer_size` parameters. It sets auto transfer to false also.
     *
     * @param transfer_count The count of transfers to perform.
     * @param buffer_size The size of the transfer buffer in bytes.
     *
     * @note This function can only be called either before `Camera::start()` or after `Camera::stop()`.
     *
     * @see ::ArducamSetTransferConfig()
     */
    bool setTransfer(int transfer_count, int buffer_size);
    /**
     * @brief Enables or disables the automatic adjusts the transfer configuration of the Arducam camera.
     *
     * @param auto_transfer A boolean value indicating whether to automatically adjust the transfer configuration or
     * not.
     *
     * @note This function can only be called either before `Camera::start()` or after `Camera::stop()`.
     */
    bool setAutoTransfer(bool auto_transfer);
    /**
     * @brief Get the recommended transfer configuration of the Arducam camera.
     *
     * @param transfer_count A ref to an integer that will store the recommended count of transfers.
     * @param buffer_size A ref to an integer that will store the recommended size of the transfer buffer in bytes.
     *
     * @note This function can only be called either before `Camera::start()` or after `Camera::stop()`.
     */
    bool getAutoTransfer(int& transfer_count, int& buffer_size) const;
    /**
     * @brief Sets the transfer memory type of the Arducam camera.
     *
     * @param mem_type The memory type to use for transfers.
     *
     * @note This function can only be called either before `Camera::start()` or after `Camera::stop()`.
     *
     * @see ::ArducamSetMemType()
     */
    bool setMemType(MemType mem_type);
    /**
     * @brief Gets the transfer memory type of the Arducam camera.
     *
     * @return a `ArducamMemType` variable indicating the memory type used for transfers.
     *
     * @see ::ArducamGetMemType()
     */
    MemType memType() const;
    /**
     * @brief Sets the force capture flag for the Arducam camera.
     *
     * This function sets the force capture flag for the Arducam camera.
     * If `force_capture` is true, the camera will capture a frame
     *   even if some error occurs during the capture process.
     * If `force_capture` is false, the camera will not.
     *
     * @param force_capture A boolean value indicating whether to force capture a frame or not.
     *
     * @see ::ArducamSetForceCapture()
     */
    void setForceCapture(bool force_capture);
    /**
     * @brief Gets the current value of the force capture flag for the Arducam camera.
     *
     * This function retrieves the current value of the force capture flag for the Arducam camera associated with the
     * given handle and stores it in the `force_capture` parameter.
     *
     * @return True if the camera is set to force capture, false otherwise.
     *
     * @see ::ArducamGetForceCapture()
     */
    bool forceCapture() const;
    /**
     * @brief Returns the last error code encountered by the Arducam camera.
     *
     * This function returns the last error code encountered by the Arducam camera. The error code is an integer value
     * that can be used to identify the type of error that occurred.
     *
     * @return The last error code encountered by the Arducam camera.
     */
    int lastError() const;
    /**
     * @brief Returns the last error messagge encountered by the Arducam camera.
     *
     * This function returns the last error message encountered by the Arducam camera. The error message is a string
     * that can be used to identify the type of error that occurred.
     *
     * @return The last error message encountered by the Arducam camera.
     *
     * @see ::ArducamErrorName()
     */
    const char* lastErrorMessage() const;
    /**
     * @brief Returns the handle to the Arducam camera.
     *
     * This function returns the handle to the Arducam camera.
     *
     * @return The handle to the Arducam camera.
     */
    const ArducamCameraHandle handle() const;

   private:
    ArducamCameraHandle handle_ = nullptr;

   protected:
    mutable std::atomic<int> last_error{0};

   public:
    /** Name of the camera. */
    const char* camera_name() const;
    /** Width of the camera. */
    uint32_t width() const;
    /** Height of the camera. */
    uint32_t height() const;
    /** Bit width of the camera. */
    uint8_t bitWidth() const;
    /**
     * @brief Format of the frame.
     *
     * The upper 8 bits represent the pixel format, and the lower 8 bits represent the bayer format.
     */
    uint16_t format() const;
    /** I2C mode of the camera. */
    uint8_t i2cMode() const;
    /** I2C address of the camera. */
    uint16_t i2cAddr() const;
};

bool is_same(Device& lhs, Device& rhs);
bool is_same(Arducam::DeviceHandle lhs, Arducam::DeviceHandle rhs);

}  // namespace Arducam

/** @} */
