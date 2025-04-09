#ifndef __ARDUCAM_USB_SDK_H__
#define __ARDUCAM_USB_SDK_H__

#ifdef __cplusplus
extern "C" {
#endif

#include <arducam_config_parser.h>
#include <stdint.h>

#if defined _MSC_VER || defined __CYGWIN__
#define ARDUCAM_EVK_DLL_IMPORT __declspec(dllimport)
#define ARDUCAM_EVK_DLL_EXPORT __declspec(dllexport)
#define ARDUCAM_EVK_DLL_LOCAL
#define ARDUCAM_EVK_CALLING __stdcall
#else
#if __GNUC__ >= 4
#define ARDUCAM_EVK_DLL_IMPORT __attribute__((visibility("default")))
#define ARDUCAM_EVK_DLL_EXPORT __attribute__((visibility("default")))
#define ARDUCAM_EVK_DLL_LOCAL  __attribute__((visibility("hidden")))
#define ARDUCAM_EVK_CALLING
#else
#define ARDUCAM_EVK_DLL_IMPORT
#define ARDUCAM_EVK_DLL_EXPORT
#define ARDUCAM_EVK_DLL_LOCAL
#define ARDUCAM_EVK_CALLING
#endif
#endif

#ifdef BUILD_EVK_LIBRARY
#define ARDUCAM_EVK_API ARDUCAM_EVK_DLL_EXPORT
#else
#define ARDUCAM_EVK_API ARDUCAM_EVK_DLL_IMPORT
#endif
#define ARDUCAM_EVK_LOCAL ARDUCAM_EVK_DLL_LOCAL

/**
 * \addtogroup Api_C
 * @{
 */

#ifdef BUILD_EVK_LIBRARY
// value
#include "values.h"
// struct
#include "structs.h"
#else
// value
#include <arducam/values.h>
// struct
#include <arducam/structs.h>
#endif

/**
 * @brief Function pointer type for a callback function to be called when an event occurs with the Arducam camera.
 *
 * @param event An ArducamEventCode enum value representing the event that occurred. (only `DeviceConnect`,
 * `DeviceDisconnect`)
 * @param device The handle to the Arducam camera device. (null if `DeviceConnect`)
 * @param user_data A void pointer to user-defined data.
 */
typedef void (*ArducamUsbEventCallback)(ArducamEventCode event, ArducamDeviceHandle device, void *user_data);
/**
 * @brief Function pointer type for a callback function to be called when a frame is capture from the camera.
 *
 * @param data The frame buffer containing the data of the capture frame.
 * @param user_data User-defined data to be passed to the callback function.
 */
typedef void (*ArducamCaptureCallback)(ArducamImageFrame data, void *user_data);
/**
 * @brief Function pointer type for a callback function to be called when an event occurs with the Arducam camera.
 *
 * @param event An ArducamEventCode enum value representing the event that occurred.
 * @param user_data A void pointer to user-defined data.
 */
typedef void (*ArducamEventCallback)(ArducamEventCode event, void *user_data);
/**
 * @brief Function pointer type for a callback function to be called when a log occurs in the camera.
 *
 * @param type The type of log that occurred.
 * @param message The message describing the log that occurred.
 * @param user_data A void pointer to user-defined data.
 */
typedef void (*ArducamMessageCallback)(ArducamLoggerLevel type, const char *error, void *user_data);

/**
 * @brief Lists all Arducam devices connected to the system and returns a handle to the device list.
 *
 * This function retrieves a list of supported Arducam devices.
 * It then creates an array of device handles and populates it with the supported devices.
 * The resulting device list handle is returned to the caller.
 *
 * @param device_list A pointer to a handle that will be set to the resulting device list.
 *
 * @note Call `ArducamFreeDeviceList()` after using the device list.
 *   If this function is called again, it will automatically call `ArducamFreeDeviceList()` to free the previous device
 * list.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamListDevice(ArducamDeviceListHandle *device_list);
/**
 * @brief Frees any existing Arducam device list and associated resources.
 *
 * This function checks if there is an existing Arducam device list and frees all resources associated with it.
 * This includes freeing the device handles and destroying the USB context.
 *
 * @note It is important to call this function after calling `ArducamListDevice()` to avoid memory leaks.
 */
ARDUCAM_EVK_API void ArducamFreeDeviceList();
/**
 * @brief Refreshes the Arducam device list.
 *
 * This function takes an Arducam device list handle and updates the list with the supported devices.
 *
 * @param device_list The Arducam device list handle to destroy.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamRefreshDeviceList(ArducamDeviceListHandle device_list);
/**
 * Registers a callback function to be called when an event occurs for the Arducam Device List.
 *
 * @param handle The handle to the Arducam camera.
 * @param callback The callback function to be called when an event occurs.
 * @param user_data User-defined data to be passed to the callback function.
 *
 * @note The hotplug event is not supported on Windows.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamDeviceListRegisterEventCallback(ArducamDeviceListHandle device_list,
                                                           ArducamUsbEventCallback callback, void *user_data);
/**
 * Clears the callback function that was previously registered to be called when an event occurs for the Arducam Device
 * List.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamDeviceListClearEventCallback(ArducamDeviceListHandle device_list);
/**
 * Checks if an event callback function has been registered for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if an event callback function has been registered, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamDeviceListHasEventCallback(ArducamDeviceListHandle device_list);
/**
 * @brief Check the devices are same or not.
 *
 * @param device1 The first device to compare.
 * @param device2 The second device to compare.
 *
 * @return `ArducamErrorCode::Success` if the devices are the same, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamIsSameDevice(ArducamDeviceHandle device1, ArducamDeviceHandle device2);
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
 * @param param Pointer to the ArducamCameraOpenParam struct to set the default values for.
 */
ARDUCAM_EVK_API void ArducamDefaultParam(ArducamCameraOpenParam *param);
/**
 * @brief Opens an Arducam camera(device) with the given parameters.
 *   Will load the configuration file and set the camera parameters.
 *   The configuration file is optional,
 *     if it is not specified, it's required to set the camera parameters manually.
 *   The extra configuration file is optional,
 *     if it is specified, it will set the camera at `init`, `start`, `stop` and `close`.
 *
 * @param out_handle Pointer to the handle of the opened camera.
 * @param param Pointer to the parameters used to open the camera.
 *
 * @note This function initializes all the necessary resources in the handle required by other functions.
 *
 * @return Returns `ArducamErrorCode::Success` if the camera was successfully opened, otherwise returns an error code.
 * Error codes:
 * - 0x0101 - Failed to read configuration file.
 * - 0x0102 - Configuration file is empty.
 * - 0x0103 - Camera configuration format error.
 * - 0x0104 - Camera control format error.
 * - 0x0201 - Failed to open camera.
 * - 0x0202 - Unknown USB type.
 * - 0x0203 - Unknown Device type.
 */
ARDUCAM_EVK_API int ArducamOpenCamera(ArducamCameraHandle *out_handle, ArducamCameraOpenParam const *param);
/**
 * @brief Initializes the Arducam camera.
 *   Must specify the camera's width, height, bit width, and format before,
 *     if no config file is loaded.
 *   Will create the io buffers and initialize the controller.
 *   Will write the configuration file to device if it is loaded.
 *   Will write the extra configuration file to device if it is loaded.
 *
 * @param handle Handle of the camera to initialize.
 *
 * @return `ArducamErrorCode::Success` if the camera was successfully initialized, otherwise an error code.
 * Error codes:
 * - 0x0301 - Failed to initialize camera.
 */
ARDUCAM_EVK_API int ArducamInitCamera(ArducamCameraHandle handle);
/**
 * @brief Closes the Arducam camera and releases all associated resources.
 *
 * This function will stop the camera if it is running
 * This function will release the USB interface, and deinitialize the controller.
 * It also releases all buffers and deletes the handle.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @note The handle is no longer valid after this function returns.
 *
 * @return `ArducamErrorCode::Success` if the camera was successfully closed, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamCloseCamera(ArducamCameraHandle handle);
/**
 * @brief Starts the Arducam camera.
 *
 * This function initializes transfers, resets the event queue, and starts the poll and event threads.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if the camera was successfully started, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamStartCamera(ArducamCameraHandle handle);
/**
 * @brief Stops the Arducam camera and releases all associated resources.
 *
 * This function sets the `do_exit` flag to true, which signals the poll and event threads to exit.
 * It also pushes an `ArducamEventCode::Exit` event to the event queue. If the event queue is full,
 * a warning is logged and the event queue is exited forcefully. The poll and event threads are then
 * joined. The function also logs a message indicating that the camera has been stopped.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if the camera was successfully stopped, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamStopCamera(ArducamCameraHandle handle);
/**
 * @brief Checks if the Arducam camera is connected to a USB 3.0 port.
 *
 * This function checks if the USB 3.0 camera device is connected to a USB 3.0 port.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if it is a USB 3.0 device connected to a USB 3.0 port
 *         or if it is a USB 2.0 device, otherwise an error code.
 * Error codes:
 * - 0x0401 - USB type mismatch.
 */
ARDUCAM_EVK_API int ArducamCheckUSBType(ArducamCameraHandle handle);
/**
 * @brief Lists the available camera configurations and their IDs.
 *
 * This function provides a list of available camera configurations and their corresponding IDs.
 *
 * @param handle The handle to the Arducam camera.
 * @param configs A pointer to an array of `ArducamCameraConfig` structures to be allocated and filled with the
 * available configurations.
 * @param ids A pointer to an array of `uint32_t` values to be allocated and filled with the IDs of the available
 * configurations.
 * @param size A pointer to a `uint32_t` value to be filled with the number of available configurations.
 *
 * @note The caller is responsible for freeing the memory allocated for the `configs` and `ids` arrays
 *       by calling `ArducamFreeModeList()`.
 *
 * @return Returns `ArducamErrorCode::Success` if the list of configurations was successfully retrieved, otherwise an
 * error code.
 */
ARDUCAM_EVK_API int ArducamListMode(ArducamCameraHandle handle, ArducamCameraConfig **configs, uint32_t **ids,
                                    uint32_t *size);
/**
 * @brief Frees the memory allocated for the camera configurations and IDs.
 *
 * @param handle The handle to the Arducam camera.
 * @param configs The pointer to the Arducam camera configurations.
 * @param ids The pointer to the Arducam camera IDs.
 *
 * @return Returns the `ArducamErrorCode::Success` if the memory was successfully freed, otherwise an error code.
 *
 * @note This function should be used to free the memory allocated by the `ArducamListMode()` function.
 *       The pointers to the configurations and IDs should be passed to this function as arguments.
 */
ARDUCAM_EVK_API int ArducamFreeModeList(ArducamCameraHandle handle, ArducamCameraConfig *configs, uint32_t *ids);
/**
 * @brief Reloads the Arducam camera with a new configuration.
 *
 * This function reloads the camera with a new configuration specified by the `mode_id` parameter.
 * It first checks if the configuration is in binary format, and returns `ArducamErrorCode::StateError` if it is not.
 * It then loads the configuration and reloads the camera with it. It also updates the `config` of
 * the camera. Finally, it reinitializes the camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param mode_id The ID of the new configuration to load.
 *
 * @return `ArducamErrorCode::Success` if the camera was successfully reloaded, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSwitchMode(ArducamCameraHandle handle, uint32_t mode_id);
/**
 * @brief Clears the buffer of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if the buffer was successfully cleared, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamClearBuffer(ArducamCameraHandle handle);
/**
 * @brief Wait a frame from the Arducam camera.
 *
 * This function wait a frame from the Arducam camera. It waits for a frame to be available in the output queue for
 * a maximum of `timeout` milliseconds. If a frame is available, it is returned.
 * If no frame is available within the timeout period, the function returns an error code.
 *
 * @param handle The handle to the Arducam camera.
 * @param timeout The maximum time to wait for a frame to be available, in milliseconds. negative value means forever.
 *
 * @return `ArducamErrorCode::Success` if a frame is available, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamWaitCaptureImage(ArducamCameraHandle handle, int timeout);
/**
 * @brief Reads a frame from the Arducam camera.
 *
 * This function reads a frame from the Arducam camera. It waits for a frame to be available in the output queue for
 * a maximum of `timeout` milliseconds. If a frame is available, it is returned in the `frame` parameter.
 * If no frame is available within the timeout period, the function returns an error code.
 *
 * @param handle The handle to the Arducam camera.
 * @param frame A pointer to an `ArducamImageFrame` struct that will be filled with the frame data.
 * @param timeout The maximum time to wait for a frame to be available, in milliseconds. negative value means forever.
 *
 * @note The caller is responsible for freeing the image by calling `ArducamFreeImage()`.
 *
 * @return `ArducamErrorCode::Success` if a frame was successfully read, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamCaptureImage(ArducamCameraHandle handle, ArducamImageFrame *frame, int timeout);
/**
 * @brief Returns a frame to the input queue of the Arducam camera.
 *
 * This function returns a frame to the input queue of the Arducam camera.
 * If the frame is invalid (i.e. the `data` field is null), the function returns an error code.
 * If the size of the frame does not match the expected size of frames for the camera,
 * the function logs an error message and drops the frame. Otherwise, the frame is added to
 * the input queue of the camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param frame The frame to return to the input queue.
 *
 * @return `ArducamErrorCode::Success` if the frame was successfully returned to the input queue, otherwise an error
 * code.
 */
ARDUCAM_EVK_API int ArducamFreeImage(ArducamCameraHandle handle, ArducamImageFrame frame);
/**
 * @brief Get the count of available frames in the output queue of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param count A pointer to an integer that will be filled with the count of available frames.
 *
 * @return `ArducamErrorCode::Success` if the count was successfully retrieved, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamAvailableImageCount(ArducamCameraHandle handle, int *count);
/**
 * @brief Registers an array of controls for the Arducam camera.
 *
 * This function registers an array of controls for the Arducam camera. The `controls` parameter is an array of
 * `Control` structs that define the controls to be registered. The `controls_length` parameter is the length of the
 * `controls` array. The caller must keep and free the `controls` array.
 *
 * @param handle The handle to the Arducam camera.
 * @param controls The array of controls to register.
 * @param controls_length The length of the `controls` array.
 *
 * @return `ArducamErrorCode::Success` if the controls were successfully registered, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamRegisterCtrls(ArducamCameraHandle handle, Control *controls, uint32_t controls_length);
/**
 * @brief Sets the value of a control for the Arducam camera.
 *
 * This function sets the value of a control for the Arducam camera. The `func_name` parameter is a string that
 * specifies the name of the control function to set. The `val` parameter is the value to set the control to.
 *
 * @param handle The handle to the Arducam camera.
 * @param func_name The name of the control function to set.
 * @param val The value to set the control to.
 *
 * @return `ArducamErrorCode::Success` if the control was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSetCtrl(ArducamCameraHandle handle, const char *func_name, int64_t val);
/**
 * @brief Retrieves an array of controls for the Arducam camera.
 *
 * This function retrieves an array of controls for the Arducam camera. The `controls` parameter is a pointer to an
 * array of `Control` structs that define the controls. The `controls_length` parameter is a pointer to the length of
 * the `controls` array. The caller must not modify or free the `controls` array, as ownership is not transferred.
 *
 * @param handle The handle to the Arducam camera.
 * @param controls A pointer to an array of `Control` structs that will be filled with the controls.
 * @param controls_length A pointer to the length of the `controls` array.
 *
 * @return `ArducamErrorCode::Success` if the controls were successfully retrieved, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamListCtrls(ArducamCameraHandle handle, const Control **controls, uint32_t *controls_length);
/**
 * @brief Clears the array of controls for the Arducam camera.
 *
 * This function clears the array of controls for the Arducam camera. The function returns 0 if the controls were
 * successfully cleared, and a negative value otherwise.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if the controls were successfully cleared, a negative value otherwise.
 */
ARDUCAM_EVK_API int ArducamClearCtrls(ArducamCameraHandle handle);
/**
 * @brief Sets the time source for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param val The time source value, which can be either `ArducamTimeSource::Firmware` or `ArducamTimeSource::System`.
 *
 * @return `ArducamErrorCode::Success` if the control was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSetTimeSource(ArducamCameraHandle handle, ArducamTimeSource val);
/**
 * Registers a callback function to be called when a frame is capture from the camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param callback The callback function to be called when a frame is capture.
 * @param user_data User-defined data to be passed to the callback function.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamRegisterCaptureCallback(ArducamCameraHandle handle, ArducamCaptureCallback callback,
                                                   void *user_data);
/**
 * Clears the callback function that was previously registered to be called when a frame is capture from the camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamClearCaptureCallback(ArducamCameraHandle handle);
/**
 * Checks if a capture callback function has been registered for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if a capture callback function has been registered, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamHasCaptureCallback(ArducamCameraHandle handle);
/**
 * Registers a callback function to be called when an event occurs for the Arducam camera.
 *
 * This function registers a callback function to be called when an event occurs for the Arducam camera.
 * If a callback function has already been registered, the function returns
 * `ArducamErrorCode::RegisterMultipleCallback`.
 *
 * @param handle The handle to the Arducam camera.
 * @param callback The callback function to be called when an event occurs.
 * @param user_data User-defined data to be passed to the callback function.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamRegisterEventCallback(ArducamCameraHandle handle, ArducamEventCallback callback,
                                                 void *user_data);
/**
 * Clears the callback function that was previously registered to be called when an event occurs for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamClearEventCallback(ArducamCameraHandle handle);
/**
 * Checks if an event callback function has been registered for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if an event callback function has been registered, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamHasEventCallback(ArducamCameraHandle handle);
/**
 * Registers a callback function to be called when an error occurs with the Arducam camera.
 * Will set the log level to `info` if it is lower than `info`.
 *
 * @param handle The handle to the Arducam camera.
 * @param callback The callback function to be called when an error occurs.
 * @param user_data User-defined data to be passed to the callback function.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamRegisterMessageCallback(ArducamCameraHandle handle, ArducamMessageCallback callback,
                                                   void *user_data);
/**
 * Clears the callback function that was previously registered to be called when an error occurs with the Arducam
 * camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamClearMessageCallback(ArducamCameraHandle handle);
/**
 * Checks if an error callback function has been registered for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if an error callback function has been registered, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamHasMessageCallback(ArducamCameraHandle handle);
/**
 * @brief Checks if the Arducam camera configuration has been loaded from a text file.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if the camera configuration has been loaded from a file,
 *         otherwise `ArducamErrorCode::StateError`.
 */
ARDUCAM_EVK_API int ArducamConfigLoaded(ArducamCameraHandle handle);
/**
 * @brief Checks if the Arducam camera binary configuration has been loaded from a binary file.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` if the camera binary configuration has been loaded,
 *         otherwise `ArducamErrorCode::StateError`.
 */
ARDUCAM_EVK_API int ArducamBinConfigLoaded(ArducamCameraHandle handle);
/**
 * @brief Returns the current capture frames per second (FPS) of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return The current capture FPS of the Arducam camera.
 */
ARDUCAM_EVK_API int ArducamGetCaptureFps(ArducamCameraHandle handle);
/**
 * @brief Returns the current bandwidth of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return The current bandwidth of the Arducam camera in bytes per second.
 */
ARDUCAM_EVK_API int ArducamGetBandwidth(ArducamCameraHandle handle);
/**
 * @brief Gets the current device of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param device A pointer to an `ArducamDeviceHandle` that will store the camera device.
 *
 * @return `ArducamErrorCode::Success` if the camera configuration was successfully retrieved, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamGetDeviceHandle(ArducamCameraHandle handle, ArducamDeviceHandle *device);
/**
 * @brief Gets the current configuration of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param config A pointer to an `ArducamCameraConfig` struct that will store the camera configuration.
 *
 * @return `ArducamErrorCode::Success` if the camera configuration was successfully retrieved, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamGetCameraConfig(ArducamCameraHandle handle, ArducamCameraConfig *config);
/**
 * @brief Sets the configuration of the Arducam camera and reloads the camera with the new configuration.
 *
 * @param handle The handle to the Arducam camera.
 * @param config A pointer to an `ArducamCameraConfig` struct that contains the camera configuration.
 *
 * @return `ArducamErrorCode::Success` if the camera configuration was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSetCameraConfig(ArducamCameraHandle handle, const ArducamCameraConfig *config);
/**
 * @brief Sets the transfer configuration of the Arducam camera.
 *
 * This function sets the transfer configuration of the Arducam camera to the values specified in the `transfer_count`
 * and `buffer_size` parameters. It sets auto transfer to false also.
 *
 * @param handle The handle to the Arducam camera.
 * @param transfer_count The count of transfers to perform.
 * @param buffer_size The size of the transfer buffer in bytes.
 *
 * @note This function can only be called either before `ArducamStartCamera()` or after `ArducamStopCamera()`.
 *
 * @return `ArducamErrorCode::Success` if the transfer configuration was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSetTransferConfig(ArducamCameraHandle handle, int transfer_count, int buffer_size);
/**
 * @brief Enables or disables the automatic adjusts the transfer configuration of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param auto_transfer A boolean value indicating whether to automatically adjust the transfer configuration or not.
 *
 * @note This function can only be called either before `ArducamStartCamera()` or after `ArducamStopCamera()`.
 *
 * @return `ArducamErrorCode::Success` if the configuration was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSetAutoTransferConfig(ArducamCameraHandle handle, bool auto_transfer);
/**
 * @brief Get the recommended transfer configuration of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param transfer_count A pointer to an integer that will store the recommended count of transfers.
 * @param buffer_size A pointer to an integer that will store the recommended size of the transfer buffer in bytes.
 *
 * @note This function can only be called either before `ArducamStartCamera()` or after `ArducamStopCamera()`.
 *
 * @return `ArducamErrorCode::Success` if the configuration was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamGetAutoTransferConfig(ArducamCameraHandle handle, int *transfer_count, int *buffer_size);
/**
 * @brief Sets the transfer memory type of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param mem_type The memory type to use for transfers.
 *
 * @note This function can only be called either before `ArducamStartCamera()` or after `ArducamStopCamera()`.
 *
 * @return `ArducamErrorCode::Success` if the configuration was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSetMemType(ArducamCameraHandle handle, ArducamMemType mem_type);
/**
 * @brief Gets the transfer memory type of the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param mem_type A pointer to a `ArducamMemType` variable indicating the memory type used for transfers.
 *
 * @return `ArducamErrorCode::Success` if the configuration was successfully retrieved, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamGetMemType(ArducamCameraHandle handle, ArducamMemType *mem_type);
/**
 * @brief Sets the force capture flag for the Arducam camera.
 *
 * This function sets the force capture flag for the Arducam camera.
 * If `force_capture` is true, the camera will capture a frame
 *   even if some error occurs during the capture process.
 * If `force_capture` is false, the camera will not.
 *
 * @param handle The handle to the Arducam camera.
 * @param force_capture A boolean value indicating whether to force capture a frame or not.
 *
 * @return `ArducamErrorCode::Success` if the force capture flag was successfully set, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamSetForceCapture(ArducamCameraHandle handle, bool force_capture);
/**
 * @brief Gets the current value of the force capture flag for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param force_capture A pointer to a boolean value that will store the current value of the force capture flag.
 *
 * @return `ArducamErrorCode::Success` if the force capture flag was successfully retrieved, otherwise an error code.
 */
ARDUCAM_EVK_API int ArducamGetForceCapture(ArducamCameraHandle handle, bool *force_capture);
/**
 * @brief Disables console logging for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamDisableConsoleLog(ArducamCameraHandle handle);
/**
 * @brief Enables console logging for the Arducam camera.
 *   Will set the log level to `info` if it is lower than `info`.
 *
 * @param handle The handle to the Arducam camera.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamEnableConsoleLog(ArducamCameraHandle handle);
/**
 * @brief Sets the log level for the Arducam camera logger.
 *
 * @param handle The handle to the Arducam camera.
 * @param level The log level to set for the logger.
 *
 * @note The library also can read the environment variable `ARDUCAM_LOG_LEVEL` to set the log level.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamSetLogLevel(ArducamCameraHandle handle, ArducamLoggerLevel level);
/**
 * @brief Gets the log level for the Arducam camera logger.
 *
 * @param handle The handle to the Arducam camera.
 * @param level The log level to set for the logger.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamGetLogLevel(ArducamCameraHandle handle, ArducamLoggerLevel *level);
/**
 * @brief Saves the log to a file for the Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param filename The name of the file to save the log to.
 *
 * @return `ArducamErrorCode::Success` on success, or an error code on failure.
 */
ARDUCAM_EVK_API int ArducamAddLogFile(ArducamCameraHandle handle, const char *filename);
/**
 * @brief Returns a string representation of the given Arducam error code.
 *
 * @param error_code The Arducam error code to get the string representation of.
 *
 * @return A string representation of the given Arducam error code.
 *         If the error code is not recognized, "*Unknown*" is returned.
 */
ARDUCAM_EVK_API const char *ArducamErrorName(int error_code);

/**
 * Returns a string representation of the USB type used by the Arducam camera
 * associated with the given handle.
 *
 * @param handle The handle of the Arducam camera to get the USB type for.
 * @return A string representation of the USB type used by the camera.
 */
ARDUCAM_EVK_API const char *ArducamGetUSBType(ArducamCameraHandle handle);

/**
 * Returns a integer representation of the USB type used by the Arducam camera
 * associated with the given handle.
 *
 * @param handle The handle of the Arducam camera to get the USB type for.
 * @return A integer representation of the USB type used by the camera.
 */
ARDUCAM_EVK_API int ArducamGetUSBTypeNumber(ArducamCameraHandle handle);

/**
 * Sends a vendor command to a camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param command The vendor command to send.
 * @param direction The `ArducamVRCommandDirection` of the transfer (either VR_HOST_TO_DEVICE or VR_DEVICE_TO_HOST).
 * @param value The value to send with the command.
 * @param index The index to send with the command.
 * @param buf_size The size of the buffer to send.
 * @param buf The buffer to send.
 * @param data_num The number of bytes transferred.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamSendVRCommand(ArducamCameraHandle handle, uint8_t command, uint8_t direction, uint16_t value,
                                         uint16_t index, uint32_t buf_size, uint8_t *buf, uint32_t *data_num);
/**
 * Sends a vendor command to set the board configuration of an Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param command The vendor command to send.
 * @param value The value to send with the command.
 * @param index The index to send with the command.
 * @param buf_size The size of the buffer to send.
 * @param buf The buffer to send.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamWriteBoardConfig(ArducamCameraHandle handle, uint8_t command, uint16_t value, uint16_t index,
                                            uint32_t buf_size, const uint8_t *buf);
/**
 * Sends a vendor command to get the board configuration of an Arducam camera.
 *
 * @param handle The handle to the Arducam camera.
 * @param command The vendor command to send.
 * @param value The value to send with the command.
 * @param index The index to send with the command.
 * @param buf_size The size of the buffer to receive.
 * @param buf The buffer to receive the board configuration.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamReadBoardConfig(ArducamCameraHandle handle, uint8_t command, uint16_t value, uint16_t index,
                                           uint32_t buf_size, uint8_t *buf);
/**
 * Writes an 8-bit value to an 8-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to write to.
 * @param val The value to write to the register.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamWriteReg_8_8(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                        uint32_t val);
/**
 * Reads an 8-bit value from an 8-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to read from.
 * @param val A pointer to the variable where the read value will be stored.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamReadReg_8_8(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                       uint32_t *val);
/**
 * Writes a 16-bit value to an 8-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to write to.
 * @param val The value to write to the register.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamWriteReg_8_16(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                         uint32_t val);
/**
 * Reads a 16-bit value from an 8-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to read from.
 * @param val A pointer to the variable where the read value will be stored.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamReadReg_8_16(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                        uint32_t *val);
/**
 * Writes a 8-bit value to an 16-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to write to.
 * @param val The value to write to the register.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamWriteReg_16_8(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                         uint32_t val);
/**
 * Reads a 8-bit value from an 16-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to read from.
 * @param val A pointer to the variable where the read value will be stored.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamReadReg_16_8(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                        uint32_t *val);
/**
 * Writes a 16-bit value to a 16-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to write to.
 * @param val The value to write to the register.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamWriteReg_16_16(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                          uint32_t val);
/**
 * Reads a 16-bit value from a 16-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to read from.
 * @param val A pointer to the variable where the read value will be stored.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamReadReg_16_16(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                         uint32_t *val);
/**
 * Writes a 32-bit value to a 16-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to write to.
 * @param val The value to write to the register.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamWriteReg_16_32(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                          uint32_t val);
/**
 * Reads a 32-bit value from a 16-bit address.
 *
 * @param handle The handle to the Arducam camera.
 * @param chip_addr The I2C slave address of the device.
 * @param reg_addr The register address to read from.
 * @param val A pointer to the variable where the read value will be stored.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamReadReg_16_32(ArducamCameraHandle handle, uint32_t chip_addr, uint32_t reg_addr,
                                         uint32_t *val);
/**
 * Writes a value to a sensor register.
 *
 * @param handle The handle to the Arducam camera.
 * @param reg_addr The register address to write to.
 * @param val The value to write to the register.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamWriteSensorReg(ArducamCameraHandle handle, uint32_t reg_addr, uint32_t val);
/**
 * Reads a value from a sensor register.
 *
 * @param handle The handle to the Arducam camera.
 * @param reg_addr The register address to read from.
 * @param val A pointer to the variable where the read value will be stored.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 */
ARDUCAM_EVK_API int ArducamReadSensorReg(ArducamCameraHandle handle, uint32_t reg_addr, uint32_t *val);
/**
 * Writes user data to the ArduCam USB device.
 *
 * @param handle The handle to the ArduCam camera.
 * @param addr The starting address of the user data to write.
 * @param len The length of the user data to write.
 * @param data A pointer to the buffer containing the user data to write.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 * - `ArducamErrorCode::UserdataAddrError` if the address is out of range
 * - `ArducamErrorCode::UserdataLenError` if the length is too long
 * - `ArducamErrorCode::VRCommandError` if the command is failed
 */
ARDUCAM_EVK_API int ArducamWriteUserData(ArducamCameraHandle handle, uint32_t addr, uint32_t len, const uint8_t *data);
/**
 * Reads user data from the ArduCam USB device.
 *
 * @param handle The handle to the ArduCam camera.
 * @param addr The starting address of the user data to read.
 * @param len The length of the user data to read.
 * @param data A pointer to the buffer where the read data will be stored.
 *
 * @return `ArducamErrorCode::Success` if the transfer was successful, otherwise returns an error code.
 * - `ArducamErrorCode::UserdataAddrError` if the address is out of range
 * - `ArducamErrorCode::UserdataLenError` if the length is too long
 * - `ArducamErrorCode::VRCommandError` if the command is failed
 */
ARDUCAM_EVK_API int ArducamReadUserData(ArducamCameraHandle handle, uint32_t addr, uint32_t len, uint8_t *data);

/** @} */

#ifdef __cplusplus
}
#endif

#endif
