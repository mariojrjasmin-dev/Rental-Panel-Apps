import { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, Modal } from 'react-native';
import DateTimePicker, { DateTimePickerEvent } from '@react-native-community/datetimepicker';

type Props = {
  date: Date;
  onDateChange: (date: Date) => void;
  minimumDate?: Date;
  label: string;
  accentColor?: string;
};

/**
 * Cross-platform date picker field.
 *
 * iOS UX: the spinner display has historically been a usability trap —
 * when shown inline it has no "Done" button, so the customer couldn't tell
 * how to save the new date and assumed the change was lost. We now present
 * the iOS picker inside a bottom-sheet modal with explicit Cancel + Done
 * buttons, and we only commit the change when the user taps Done. The
 * Android UX keeps the OS's native modal (it already includes OK/Cancel).
 */
export default function DatePickerField({ date, onDateChange, minimumDate, label, accentColor = '#FF3B30' }: Props) {
  const [show, setShow] = useState(false);
  // Temporary value used by the iOS spinner. We don't propagate the change
  // to the parent until the user taps "Done" — gives them a real cancel path.
  const [tempDate, setTempDate] = useState<Date>(date);

  const openPicker = () => {
    setTempDate(date); // start from the currently-saved date
    setShow(true);
  };

  // Android: the native picker is already modal with OK/Cancel.
  const onAndroidChange = (event: DateTimePickerEvent, selectedDate?: Date) => {
    setShow(false); // native picker dismissed
    if (event.type === 'set' && selectedDate) {
      onDateChange(selectedDate);
    }
  };

  // iOS spinner: just track the in-flight selection. We commit on Done.
  const onIOSChange = (_event: DateTimePickerEvent, selectedDate?: Date) => {
    if (selectedDate) setTempDate(selectedDate);
  };

  const formatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <View>
      <TouchableOpacity
        testID={`date-picker-${label.toLowerCase().replace(/\s/g, '-')}`}
        style={styles.trigger}
        onPress={openPicker}
        activeOpacity={0.7}
      >
        <View style={[styles.dot, { backgroundColor: accentColor }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>{label}</Text>
          <Text style={styles.dateText}>{formatted}</Text>
        </View>
        <TouchableOpacity onPress={openPicker} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Text style={[styles.changeBtn, { color: accentColor }]}>Change</Text>
        </TouchableOpacity>
      </TouchableOpacity>

      {/* Android: the OS picker is already a dialog with OK/Cancel buttons. */}
      {show && Platform.OS === 'android' && (
        <DateTimePicker
          testID={`datetime-picker-${label.toLowerCase().replace(/\s/g, '-')}`}
          value={date}
          mode="date"
          display="default"
          onChange={onAndroidChange}
          minimumDate={minimumDate}
          accentColor={accentColor}
        />
      )}

      {/* iOS: present the spinner inside a bottom-sheet modal with our own
          Cancel / Done buttons. This is the standard iOS pattern (App Store
          apps use it) and fixes the "user can't save the new date" issue. */}
      <Modal
        visible={show && Platform.OS === 'ios'}
        transparent
        animationType="fade"
        onRequestClose={() => setShow(false)}
      >
        <View style={styles.iosOverlay}>
          <TouchableOpacity style={styles.iosBackdrop} activeOpacity={1} onPress={() => setShow(false)} />
          <View style={styles.iosSheet}>
            <View style={styles.iosHeader}>
              <TouchableOpacity onPress={() => setShow(false)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                <Text style={styles.iosCancel}>Cancel</Text>
              </TouchableOpacity>
              <Text style={styles.iosTitle}>{label}</Text>
              <TouchableOpacity
                testID={`datetime-picker-done-${label.toLowerCase().replace(/\s/g, '-')}`}
                onPress={() => {
                  onDateChange(tempDate);
                  setShow(false);
                }}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <Text style={[styles.iosDone, { color: accentColor }]}>Done</Text>
              </TouchableOpacity>
            </View>
            <DateTimePicker
              testID={`datetime-picker-${label.toLowerCase().replace(/\s/g, '-')}`}
              value={tempDate}
              mode="date"
              display="spinner"
              onChange={onIOSChange}
              minimumDate={minimumDate}
              accentColor={accentColor}
              themeVariant="light"
              style={styles.iosPicker}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
    padding: 16,
    borderRadius: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: '#E5E5E5',
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  label: { fontSize: 10, color: '#999', fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  dateText: { fontSize: 16, fontWeight: '700', color: '#0A0A0A', marginTop: 2 },
  changeBtn: { fontSize: 14, fontWeight: '700' },
  // ---- iOS bottom-sheet picker ----
  iosOverlay: { flex: 1, justifyContent: 'flex-end' },
  iosBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.45)' },
  iosSheet: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingBottom: 24,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
  },
  iosHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F0F0',
  },
  iosTitle: { fontSize: 16, fontWeight: '800', color: '#0A0A0A', flex: 1, textAlign: 'center' },
  iosCancel: { fontSize: 15, fontWeight: '600', color: '#666' },
  iosDone: { fontSize: 15, fontWeight: '800' },
  iosPicker: { width: '100%' },
});
