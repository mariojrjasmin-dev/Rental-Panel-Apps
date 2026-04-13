import { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import DateTimePicker, { DateTimePickerEvent } from '@react-native-community/datetimepicker';

type Props = {
  date: Date;
  onDateChange: (date: Date) => void;
  minimumDate?: Date;
  label: string;
  accentColor?: string;
};

export default function DatePickerField({ date, onDateChange, minimumDate, label, accentColor = '#FF3B30' }: Props) {
  const [show, setShow] = useState(false);

  const onChange = (event: DateTimePickerEvent, selectedDate?: Date) => {
    setShow(Platform.OS === 'ios');
    if (selectedDate) {
      onDateChange(selectedDate);
    }
  };

  const formatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <View>
      <TouchableOpacity
        testID={`date-picker-${label.toLowerCase().replace(/\s/g, '-')}`}
        style={styles.trigger}
        onPress={() => setShow(true)}
        activeOpacity={0.7}
      >
        <View style={[styles.dot, { backgroundColor: accentColor }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>{label}</Text>
          <Text style={styles.dateText}>{formatted}</Text>
        </View>
        <TouchableOpacity onPress={() => setShow(true)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Text style={[styles.changeBtn, { color: accentColor }]}>Change</Text>
        </TouchableOpacity>
      </TouchableOpacity>

      {show && (
        <DateTimePicker
          testID={`datetime-picker-${label.toLowerCase().replace(/\s/g, '-')}`}
          value={date}
          mode="date"
          display={Platform.OS === 'ios' ? 'spinner' : 'default'}
          onChange={onChange}
          minimumDate={minimumDate}
          accentColor={accentColor}
        />
      )}
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
});
